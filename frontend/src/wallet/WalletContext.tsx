import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { BrowserProvider, Contract, keccak256, toUtf8Bytes, getAddress, type Eip1193Provider } from 'ethers'
import { api } from '../api'

type Ethereum = Eip1193Provider & {
  on?: (event: string, handler: (...args: any[]) => void) => void
  removeListener?: (event: string, handler: (...args: any[]) => void) => void
}
declare global { interface Window { ethereum?: Ethereum } }

const HARDHAT_CHAIN = '0x7a69'
const ROLE_NAMES = ['DATASET_PROVIDER_ROLE', 'MODEL_DEVELOPER_ROLE', 'AUDITOR_ROLE', 'DEPLOYMENT_OPERATOR_ROLE'] as const
const ROLE_ABI = ['function hasRole(bytes32 role, address account) view returns (bool)', 'function DEFAULT_ADMIN_ROLE() view returns (bytes32)']

type WalletContextValue = {
  address: string | null
  chainId: number | null
  roles: string[]
  pending: boolean
  error: string | null
  connect: () => Promise<void>
  switchToHardhat: () => Promise<void>
  disconnect: () => void
  refresh: () => Promise<void>
  sendPrepared: (transaction: PreparedTx) => Promise<string>
}
export type PreparedTx = { from: string; to: string; data: string; value: string; chain_id: number }
const Context = createContext<WalletContextValue | null>(null)
export function useWallet() { const ctx = useContext(Context); if (!ctx) throw new Error('WalletProvider missing'); return ctx }

export function WalletProvider({children}: {children: ReactNode}) {
  const [address, setAddress] = useState<string | null>(null)
  const [chainId, setChainId] = useState<number | null>(null)
  const [roles, setRoles] = useState<string[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const eth = window.ethereum
    if (!eth) { setAddress(null); setRoles([]); setChainId(null); return }
    try {
      const provider = new BrowserProvider(eth)
      const accounts = await provider.send('eth_accounts', []) as string[]
      const network = await provider.getNetwork()
      setChainId(Number(network.chainId))
      if (!accounts.length) { setAddress(null); setRoles([]); return }
      const wallet = getAddress(accounts[0])
      setAddress(wallet)
      if (Number(network.chainId) !== 31337) { setRoles([]); return }
      const status = await api.status()
      if (!status.contract_deployed || !status.contract_address) { setRoles([]); return }
      const contract = new Contract(status.contract_address, ROLE_ABI, provider)
      const granted: string[] = []
      const admin = await contract.DEFAULT_ADMIN_ROLE() as string
      if (await contract.hasRole(admin, wallet)) granted.push('Admin')
      for (const role of ROLE_NAMES) {
        if (await contract.hasRole(keccak256(toUtf8Bytes(role)), wallet)) granted.push(role.replace('_ROLE','').replaceAll('_',' '))
      }
      setRoles(granted)
      setError(null)
    } catch (err) { setError((err as Error).message); setRoles([]) }
  }, [])

  useEffect(() => {
    const eth = window.ethereum
    if (!eth) return
    const changed = () => { void refresh() }
    eth.on?.('accountsChanged', changed)
    eth.on?.('chainChanged', changed)
    void refresh()
    return () => {
      eth.removeListener?.('accountsChanged', changed)
      eth.removeListener?.('chainChanged', changed)
    }
  }, [refresh])

  const connect = useCallback(async () => {
    if (!window.ethereum) { setError('MetaMask was not detected. Install or enable the extension.'); return }
    setPending(true); setError(null)
    try { await window.ethereum.request({method: 'eth_requestAccounts'}); await refresh() }
    catch (err) { setError((err as Error).message) }
    finally { setPending(false) }
  }, [refresh])

  const switchToHardhat = useCallback(async () => {
    if (!window.ethereum) { setError('MetaMask not detected'); return }
    setPending(true); setError(null)
    try {
      try { await window.ethereum.request({method:'wallet_switchEthereumChain',params:[{chainId:HARDHAT_CHAIN}]}) }
      catch (err) {
        if ((err as {code?:number}).code !== 4902) throw err
        await window.ethereum.request({method:'wallet_addEthereumChain',params:[{
          chainId:HARDHAT_CHAIN, chainName:'Hardhat Local', rpcUrls:['http://127.0.0.1:8545'],
          nativeCurrency:{name:'Ether',symbol:'ETH',decimals:18}
        }]})
        await window.ethereum.request({method:'wallet_switchEthereumChain',params:[{chainId:HARDHAT_CHAIN}]})
      }
      await refresh()
    } catch (err) {setError((err as Error).message)} finally {setPending(false)}
  }, [refresh])

  // MetaMask does not expose a reliable programmatic disconnect/revoke API.
  // This clears only the app's displayed state; MetaMask manages permissions.
  const disconnect = useCallback(() => {setAddress(null); setRoles([])}, [])

  const sendPrepared = useCallback(async (transaction: PreparedTx) => {
    if (!window.ethereum || !address) throw new Error('Connect MetaMask first.')
    const status = await api.status()
    if (!status.contract_deployed || !status.contract_address) throw new Error('Contract unavailable.')
    if (Number(transaction.chain_id) !== 31337 || status.chain_id !== 31337) throw new Error('Hardhat chain ID mismatch.')
    const provider = new BrowserProvider(window.ethereum)
    if (Number((await provider.getNetwork()).chainId) !== 31337) throw new Error('Switch MetaMask to Hardhat Local.')
    if (getAddress(transaction.from) !== getAddress(address)) throw new Error('Prepared transaction sender differs from connected wallet.')
    if (getAddress(transaction.to) !== getAddress(status.contract_address)) throw new Error('Unexpected contract destination.')
    if (!/^0x[0-9a-fA-F]*$/.test(transaction.data) || !transaction.data.startsWith('0x')) throw new Error('Invalid transaction data.')
    if (BigInt(transaction.value) !== 0n) throw new Error('Unexpected ETH value.')
    const signer = await provider.getSigner()
    const sent = await signer.sendTransaction({to: transaction.to, data: transaction.data, value: 0n})
    // Report the hash before waiting so the user can recover confirmation on timeout.
    const receipt = await sent.wait()
    if (!receipt || receipt.status !== 1) throw new Error(`Transaction failed or was not mined. Hash: ${sent.hash}`)
    return sent.hash
  }, [address])

  const value = useMemo(() => ({address,chainId,roles,pending,error,connect,switchToHardhat,disconnect,refresh,sendPrepared}),
    [address,chainId,roles,pending,error,connect,switchToHardhat,disconnect,refresh,sendPrepared])
  return <Context.Provider value={value}>{children}</Context.Provider>
}

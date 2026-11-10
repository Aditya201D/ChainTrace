import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("ChainTraceRegistryModule", m => {
    const registry = m.contract("ChainTraceRegistry");

    return { registry };
});

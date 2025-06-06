from xdsl.passes import ModulePass
from xdsl.ir import MLContext

from inconspiquous.dialects.qssa import QSSACircuitOp, QSSADynGateOp, QSSAReturnOp

class InlineCircuitPass(ModulePass):
    """
    This pass inlines qssa.circuit definitions at their call sites.
    It replaces any `qssa.dyn_gate` that calls a `qssa.circuit` with the
    body of that circuit.
    """
    name = "inline-circuits"

    def apply(self, ctx: MLContext, module):
        # We walk the module to find all circuit definitions first
        # This is safer than modifying the IR while iterating over it.
        circuits_to_erase = set()

        # We must iterate over a copy of the operations, as we will be modifying them
        for circuit_op in list(module.walk(QSSACircuitOp)):
            
            # Find all uses of the gate produced by this circuit
            # We also make a copy of the uses list, as it will change during iteration
            uses = list(circuit_op.gate.uses)
            
            # If there are no uses, we can't do anything yet.
            # A separate dead code elimination pass would remove the unused circuit.
            if not uses:
                continue

            for use in uses:
                dyn_gate_op = use.operation
                # This pass only targets qssa.dyn_gate calls
                if not isinstance(dyn_gate_op, QSSADynGateOp):
                    continue 

                # --- The Inlining Logic ---
                circuit_block = circuit_op.body.block
                
                # 1. Replace all uses of the circuit's arguments with the gate's qubit inputs
                for circuit_arg, gate_arg in zip(circuit_block.args, dyn_gate_op.qubits):
                    circuit_arg.replace_all_uses_with(gate_arg)

                # 2. The terminator is the last operation in the circuit's block
                return_op = circuit_block.last_op
                assert isinstance(return_op, QSSAReturnOp), "Circuit must end with qssa.return"

                # 3. Replace all uses of the dynamic gate's results with the circuit's return values
                for gate_result, return_val in zip(dyn_gate_op.results, return_op.qubits):
                    gate_result.replace_all_uses_with(return_val)

                # 4. Move the operations from the circuit body to before the gate call
                for op_in_circuit in list(circuit_block.ops)[:-1]: # All ops except the qssa.return
                    op_in_circuit.detach()
                    dyn_gate_op.parent.insert_op_before(op_in_circuit, dyn_gate_op)
                
                # 5. Erase the dynamic gate call itself, as it has been fully replaced
                dyn_gate_op.erase()
                
            # Once all uses of a circuit have been inlined, mark it for deletion.
            circuits_to_erase.add(circuit_op)

        # After inlining all uses, erase the (now unused) circuit definitions
        for op in circuits_to_erase:
            op.erase()
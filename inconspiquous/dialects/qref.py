from typing import ClassVar
from xdsl.dialects.builtin import i1
from xdsl.ir import Dialect, Operation, SSAValue
from xdsl.irdl import (
    AnyInt,
    IRDLOperation,
    IntVarConstraint,
    RangeOf,
    irdl_op_definition,
    operand_def,
    prop_def,
    traits_def,
    var_operand_def,
    eq,
    var_result_def,
)
from xdsl.pattern_rewriter import RewritePattern, PatternRewriteWalker, op_type_rewrite_pattern
from xdsl.traits import HasCanonicalizationPatternsTrait

from inconspiquous.dialects.gate import GateType
from inconspiquous.dialects.measurement import CompBasisMeasurementAttr, MeasurementType
from inconspiquous.gates import GateAttr
from inconspiquous.dialects.qu import BitType
from inconspiquous.constraints import SizedAttributeConstraint
from inconspiquous.measurement import MeasurementAttr
from xdsl.passes import ModulePass
from inconspiquous.dialects.qssa import QSSACircuitOp, QSSADynGateOp, QSSAReturnOp


@irdl_op_definition
class GateOp(IRDLOperation):
    name = "qref.gate"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    gate = prop_def(SizedAttributeConstraint(GateAttr, _I))

    ins = var_operand_def(RangeOf(eq(BitType()), length=_I))

    assembly_format = "`<` $gate `>` $ins attr-dict"

    def __init__(self, gate: GateAttr, *ins: SSAValue | Operation):
        super().__init__(
            operands=[ins],
            properties={
                "gate": gate,
            },
        )


class DynGateOpHasCanonicalizationPatterns(HasCanonicalizationPatternsTrait):
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from inconspiquous.transforms.canonicalization.qref import DynGateConst

        return (DynGateConst(),)

class InlineCircuitPass(ModulePass):
    """
    This pass inlines qssa.circuit definitions at their call sites.
    """
    name = "inline-circuits"

    def apply(self, module):
        # We walk the module to find all circuit definitions first
        circuits_to_erase = set()

        for circuit_op in module.walk(QSSACircuitOp):
            # Find all uses of the gate produced by this circuit
            uses = list(circuit_op.gate.uses)
            
            for use in uses:
                dyn_gate_op = use.operation
                if not isinstance(dyn_gate_op, QSSADynGateOp):
                    continue # Not a dynamic gate call, skip

                # --- The Inlining Logic ---
                circuit_block = circuit_op.body.block
                
                # 1. Replace uses of the circuit's arguments with the gate's qubit inputs
                for circuit_arg, gate_arg in zip(circuit_block.args, dyn_gate_op.qubits):
                    circuit_arg.replace_all_uses_with(gate_arg)

                # 2. Replace uses of the dynamic gate's results with the circuit's return values
                return_op = circuit_block.last_op
                for gate_result, return_val in zip(dyn_gate_op.results, return_op.qubits):
                    gate_result.replace_all_uses_with(return_val)

                # 3. Move the operations from the circuit body to before the gate call
                for op_in_circuit in list(circuit_block.ops)[:-1]: # All except the qssa.return
                    op_in_circuit.detach()
                    dyn_gate_op.parent.insert_op_before(op_in_circuit, dyn_gate_op)
                
                # 4. Erase the dynamic gate call itself
                dyn_gate_op.erase()
                
            circuits_to_erase.add(circuit_op)

        # After inlining all uses, erase the (now unused) circuit definitions
        for op in circuits_to_erase:
            op.erase()


@irdl_op_definition
class DynGateOp(IRDLOperation):
    name = "qref.dyn_gate"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    gate = operand_def(GateType.constr(_I))

    ins = var_operand_def(RangeOf(eq(BitType()), length=_I))

    assembly_format = "`<` $gate `>` $ins attr-dict"

    traits = traits_def(DynGateOpHasCanonicalizationPatterns())

    def __init__(self, gate: SSAValue | Operation, *ins: SSAValue | Operation):
        super().__init__(
            operands=[gate, ins],
        )


@irdl_op_definition
class MeasureOp(IRDLOperation):
    name = "qref.measure"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    measurement = prop_def(
        SizedAttributeConstraint(MeasurementAttr, _I),
        default_value=CompBasisMeasurementAttr(),
    )

    in_qubits = var_operand_def(RangeOf(eq(BitType()), length=_I))

    outs = var_result_def(RangeOf(eq(i1), length=_I))

    assembly_format = "(`` `<` $measurement^ `>`)? $in_qubits attr-dict"

    def __init__(
        self,
        *in_qubits: SSAValue | Operation,
        measurement: MeasurementAttr = CompBasisMeasurementAttr(),
    ):
        super().__init__(
            properties={
                "measurement": measurement,
            },
            operands=(in_qubits,),
            result_types=((i1,) * len(in_qubits)),
        )


class DynMeasureOpHasCanonicalizationPatterns(HasCanonicalizationPatternsTrait):
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from inconspiquous.transforms.canonicalization.qref import (
            DynMeasureConst,
        )

        return (DynMeasureConst(),)


@irdl_op_definition
class DynMeasureOp(IRDLOperation):
    name = "qref.dyn_measure"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    measurement = operand_def(MeasurementType.constr(_I))

    in_qubits = var_operand_def(RangeOf(eq(BitType()), length=_I))

    outs = var_result_def(RangeOf(eq(i1), length=_I))

    assembly_format = "`<` $measurement `>` $in_qubits attr-dict"

    traits = traits_def(DynMeasureOpHasCanonicalizationPatterns())

    def __init__(
        self, *in_qubits: SSAValue | Operation, measurement: SSAValue | Operation
    ):
        super().__init__(
            operands=[measurement, in_qubits],
            result_types=(tuple(i1 for _ in in_qubits),),
        )


Qref = Dialect(
    "qref",
    [
        GateOp,
        DynGateOp,
        MeasureOp,
        DynMeasureOp,
    ],
    [],
)

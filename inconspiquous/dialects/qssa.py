from typing import ClassVar
from xdsl.dialects.builtin import i1
from xdsl.ir import Dialect, Operation, SSAValue, OpResult
from xdsl.irdl import (
    AnyInt,
    IRDLOperation,
    IntVarConstraint,
    RangeOf,
    irdl_op_definition,
    operand_def,
    prop_def,
    result_def,
    traits_def,
    var_operand_def,
    var_result_def,
    eq,
    SingleBlockRegion,
    VarOperand,
    region_def
)
from xdsl.pattern_rewriter import RewritePattern
from xdsl.traits import HasCanonicalizationPatternsTrait, IsTerminator

from inconspiquous.dialects.gate import GateType
from inconspiquous.dialects.measurement import CompBasisMeasurementAttr, MeasurementType
from inconspiquous.gates import GateAttr
from inconspiquous.dialects.qu import BitType
from inconspiquous.constraints import SizedAttributeConstraint
from inconspiquous.measurement import MeasurementAttr


class GateOpHasCanonicalizationPatterns(HasCanonicalizationPatternsTrait):
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from inconspiquous.transforms.canonicalization.qssa import GateIdentity

        return (GateIdentity(),)


@irdl_op_definition
class QSSAReturnOp(IRDLOperation):
    name = "qssa.return"

    # A variable number of qubits being returned
    qubits: VarOperand = var_operand_def(BitType)
    
    # The 'traits' definition is now correctly placed inside the class body
    traits = traits_def(IsTerminator())


@irdl_op_definition
class QSSACircuitOp(IRDLOperation):
    name = "qssa.circuit"

    body: SingleBlockRegion = region_def()
    gate: OpResult = result_def(GateType)

    def verify_(self):
        if not self.body.block:
            raise Exception("qssa.circuit body cannot be empty")
        
        num_inputs = len(self.body.block.args)
        for arg in self.body.block.args:
            if not isinstance(arg.typ, BitType):
                raise Exception("qssa.circuit arguments must be of type !qu.bit")
        
        terminator = self.body.block.last_op
        if not isinstance(terminator, QSSAReturnOp):
            raise Exception("qssa.circuit must be terminated by qssa.return")
            
        num_outputs = len(terminator.qubits)
        gate_size = self.gate.typ.n.data

        if not (num_inputs == num_outputs == gate_size):
            raise Exception(f"Inconsistent qubit counts: "
                            f"gate type has {gate_size}, "
                            f"circuit has {num_inputs} inputs, "
                            f"and returns {num_outputs} outputs.")


@irdl_op_definition
class GateOp(IRDLOperation):
    name = "qssa.gate"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    gate = prop_def(SizedAttributeConstraint(GateAttr, _I))

    ins = var_operand_def(RangeOf(eq(BitType()), length=_I))

    outs = var_result_def(RangeOf(eq(BitType()), length=_I))

    assembly_format = "`<` $gate `>` $ins attr-dict"

    traits = traits_def(GateOpHasCanonicalizationPatterns())

    def __init__(self, gate: GateAttr, *ins: SSAValue | Operation):
        super().__init__(
            operands=[ins],
            properties={
                "gate": gate,
            },
            result_types=(tuple(BitType() for _ in ins),),
        )


class DynGateOpHasCanonicalizationPatterns(HasCanonicalizationPatternsTrait):
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from inconspiquous.transforms.canonicalization.qssa import (
            DynGateConst,
            DynGateCompose,
        )

        return (DynGateConst(), DynGateCompose())


@irdl_op_definition
class DynGateOp(IRDLOperation):
    name = "qssa.dyn_gate"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    gate = operand_def(GateType.constr(_I))

    ins = var_operand_def(RangeOf(eq(BitType()), length=_I))

    outs = var_result_def(RangeOf(eq(BitType()), length=_I))

    assembly_format = "`<` $gate `>` $ins attr-dict"

    traits = traits_def(DynGateOpHasCanonicalizationPatterns())

    def __init__(self, gate: SSAValue | Operation, *ins: SSAValue | Operation):
        super().__init__(
            operands=[gate, ins],
            result_types=(tuple(BitType() for _ in ins),),
        )


@irdl_op_definition
class MeasureOp(IRDLOperation):
    name = "qssa.measure"

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
        from inconspiquous.transforms.canonicalization.qssa import (
            DynMeasureConst,
        )

        return (DynMeasureConst(),)


@irdl_op_definition
class DynMeasureOp(IRDLOperation):
    name = "qssa.dyn_measure"

    _I: ClassVar = IntVarConstraint("I", AnyInt())

    measurement = operand_def(MeasurementType.constr(_I))

    in_qubits = var_operand_def(RangeOf(eq(BitType()), length=_I))

    outs = var_result_def(RangeOf(eq(i1), length=_I))

    assembly_format = "`<` $measurement `>` $in_qubits attr-dict"

    traits = traits_def(DynMeasureOpHasCanonicalizationPatterns())

    def __init__(
        self,
        *in_qubits: SSAValue | Operation,
        measurement: SSAValue | Operation,
    ):
        super().__init__(
            operands=[measurement, in_qubits],
            result_types=(tuple(i1 for _ in in_qubits),),
        )


Qssa = Dialect(
    "qssa",
    [
        GateOp,
        DynGateOp,
        MeasureOp,
        DynMeasureOp,
    ],
    [],
)

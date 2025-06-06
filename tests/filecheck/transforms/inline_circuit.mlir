// RUN: quopt -p inline-circuits %s | filecheck %s

// This test defines a 2-qubit circuit that acts like a CNOT gate.
// It then calls this circuit and verifies that the inliner pass correctly
// replaces the `qssa.dyn_gate` with the body of the circuit.

// CHECK-LABEL: func.func @main() {
// CHECK-NEXT:    %0 = "qu.alloc"() : () -> !qu.bit
// CHECK-NEXT:    %1 = "qu.alloc"() : () -> !qu.bit
// CHECK-DAG:     %cnot_ctrl = qssa.gate<#gate.cnot> %0
// CHECK-DAG:     %cnot_target = qssa.gate<#gate.cnot> %1
// CHECK-NEXT:    qssa.gate<#gate.h> %cnot_ctrl
// CHECK-NEXT:    func.return
// CHECK-NEXT:  }
func.func @main() {
  %0 = "qu.alloc"() : () -> !qu.bit
  %1 = "qu.alloc"() : () -> !qu.bit

  %cnot_circuit = "qssa.circuit"() : () -> !gate.type<2> {
  ^bb0(%ctrl: !qu.bit, %target: !qu.bit):
    %cnot_ctrl = qssa.gate<#gate.cnot> %ctrl
    %cnot_target = qssa.gate<#gate.cnot> %target
    qssa.return %cnot_ctrl, %cnot_target
  }

  %2, %3 = "qssa.dyn_gate"(%cnot_circuit, %0, %1) : (!gate.type<2>, !qu.bit, !qu.bit) -> (!qu.bit, !qu.bit)
  
  // Use one of the output qubits to show connections are maintained
  qssa.gate<#gate.h> %2

  func.return
}

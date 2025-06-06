// --- TEST FOR QSSA CIRCUIT ---

// CHECK-LABEL: func.func @test_qssa_circuit() {
// CHECK-NEXT:    %my_circuit = "qssa.circuit"() : () -> !gate.type<2> {
// CHECK-NEXT:    ^bb0(%0: !qu.bit, %1: !qu.bit):
// CHECK-NEXT:      %2 = qssa.gate<#gate.h> %0
// CHECK-NEXT:      qssa.return %2, %1
// CHECK-NEXT:    }
// CHECK-NEXT:    func.return
// CHECK-NEXT:  }
func.func @test_qssa_circuit() {
  %my_circuit = "qssa.circuit"() : () -> !gate.type<2> {
  ^bb0(%arg0: !qu.bit, %arg1: !qu.bit):
    %res0 = qssa.gate<#gate.h> %arg0
    qssa.return %res0, %arg1
  }
  func.return
}

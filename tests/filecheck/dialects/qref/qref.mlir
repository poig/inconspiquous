// --- TEST FOR QREF CIRCUIT ---

// CHECK-LABEL: func.func @test_qref_circuit() {
// CHECK-NEXT:    %my_circuit = "qref.circuit"() : () -> !gate.type<1> {
// CHECK-NEXT:    ^bb0(%0: !qu.bit):
// CHECK-NEXT:      qref.gate<#gate.x> %0
// CHECK-NEXT:      qref.return
// CHECK-NEXT:    }
// CHECK-NEXT:    func.return
// CHECK-NEXT:  }
func.func @test_qref_circuit() {
  %my_circuit = "qref.circuit"() : () -> !gate.type<1> {
  ^bb0(%arg0: !qu.bit):
    qref.gate<#gate.x> %arg0
    qref.return
  }
  func.return
}
# MOSAIC Execution–Closure Binding

أصبح تنفيذ MOSAIC مرتبطًا فعليًا بمسار الإغلاق. `MosaicProtocol.apply_execution` لا يسمح بتثبيت execution receipt إلا بعد تحقق `ClosureProof`. ويتحقق المسار من أن predecessor seal معروف، وأن `executor.state_root` يطابق predecessor state root، وأن `Capsule.rule_witness` يساوي transaction id، وأن `ExecutionReceipt.post_state_root` يساوي `Capsule.successor_root`.

بعد نجاح التنفيذ يُستدعى `protocol.apply` لإنشاء `StateSeal` التالي، ثم يُنشأ `ExecutionBinding` مربوط بـcapsule وpredecessor. وإذا فشل أي شرط، تُستعاد state وnonces وreceipts الخاصة بالexecutor ولا يتغير protocol current seal.

أضيفت أيضًا `DeterministicExecutor.persist` و`from_store` لاستعادة state root وnonces وreceipts من DurableStore بعد restart. اختُبر المسار end-to-end، ورفض rule witness الخاطئ، وatomic rollback، واستعادة التنفيذ عبر WAL.

> kernel الحالية ما زالت bounded instruction set (`SET`, `DELETE`, `ADD_INT`) وليست VM عقود ذكية عامة. هذا القيد متعمد حتى تصبح state transition وclosure binding قابلة للإثبات قبل توسيع اللغة أو إدخال bytecode sandbox.

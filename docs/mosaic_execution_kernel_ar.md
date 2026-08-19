# MOSAIC Deterministic Execution Kernel

أضيف إلى MOSAIC نواة تنفيذ deterministic محدودة بدل تشغيل كود غير موثوق داخل العقد. العمليات المدعومة حاليًا هي `SET` و`DELETE` و`ADD_INT` فقط، مع حدود حجم للمفاتيح والقيم وعدد التعليمات، وحساب gas، وnonce لكل caller، وتحقق Ed25519، وstate root، وevent root، وstate diff digest.

يُنفذ كل transaction على نسخة staged من الحالة. إذا فشل التحقق أو nonce أو gas أو العملية، لا تُثبت أي كتابة. وتنفذ `execute_batch` مجموعة المعاملات atomic؛ فإذا فشل عنصر واحد تُستعاد الحالة والـnonces والـreceipts السابقة.

> هذه النواة ليست بعد آلة عقود ذكية Turing-complete، ولا تدعي أنها بديل كامل لـEVM أو Move VM. اختيار instruction set محدود متعمد في هذه المرحلة لتقليل مساحة الهجوم وإثبات deterministic execution قبل إضافة لغة عقود أو bytecode sandbox.

الخطوة التالية المطلوبة قبل اعتبار التنفيذ جزءًا من شبكة عامة هي ربط `ExecutionReceipt` بـCapsule وClosureProof، بحيث لا تصبح نتيجة التنفيذ قابلة للصرف إلا بعد إغلاق predecessor والتحقق من `pre_state_root` و`post_state_root`. كما يجب إضافة resource accounting واقعي، persistence للحالة، replay-safe execution عبر restart، واختبارات cross-resource composability.

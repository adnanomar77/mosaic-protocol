# MOSAIC Randomness Incentives

أضيف `RandomnessIncentiveManager` لتسوية دورة randomness كاملة بدل الاكتفاء بإنتاج beacon. عند بلوغ reveal weight النصاب، يُنشأ beacon من الأسرار المكشوفة، ويُكافأ validators الذين كشفوا أسرارهم، بينما يُعاقب non-reveal عبر `SettlementLedger` ويُخفض stake في `MembershipManager`.

عند عدم بلوغ reveal weight النصاب، لا يتوقف liveness تلقائيًا. إذا كان commitment weight نفسه نصابيًا، يُنشأ `commitment-fallback` beacon من commitments الموقعة. لا يُعاقب validator الذي كشف سره حتى لو لم تكفِ reveals وحدها للنصاب؛ العقوبة تطبق فقط على non-reveal الحقيقي. ويظل fallback مرتبطًا بـepoch وround وcommitment IDs وقابلًا للتحقق من proof_id.

تمنع السياسة إعادة تطبيق penalty عبر `non_reveal_history` في العضوية و`slash_evidence_ids` في settlement ledger، كما تمنع توزيع مكافآت epoch مرتين. الاختبارات تغطي المسار الكامل، fallback، رفض commitment weight غير النصابي، وتطابق stake والـbond بعد العقوبة.

> fallback لا يثبت تلقائيًا أن beacon متحيز ضد جميع adversaries؛ يجب في شبكة عامة تحديد commit window، reveal window، حوافز عدم الكشف، وتوزيع الرسوم، وإثبات أن أي مجموعة أقل من ثلث الوزن لا تستطيع التحكم في النتيجة أو تعطيلها اقتصاديًا.

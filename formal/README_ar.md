# Formal verification status

الملف `mosaic_safety.tla` يعرّف آلة حالة مجردة لخصائص MOSAIC الأساسية: عدم وجود إغلاقين، عدم التطبيق دون proof، تحويل التعارض إلى evidence، الفصل بين closure وabandon، quorum availability، وatomic execution.

في البيئة الحالية لا يوجد TLC مثبت، لذلك لم يُعلن اجتياز TLA+ رسمي. بوابة التنفيذ المتاحة هي `benchmarks/model_check_mosaic.py`، وقد نجحت فيها الحالات المحدودة M1–M8، بما في ذلك 84 حالة و36,703 زوج quorums في فحص تقاطع النصاب. يجب لاحقًا تثبيت TLC أو استخدام Apalache وتشغيل invariant checking على constants صغيرة، ثم ربط نتائج checker بالمواصفة والـwire objects الفعلية.

> bounded model checking يثبت عدم وجود counterexample داخل الفضاء المحدد فقط. لا يحول ذلك وحده إلى برهان عام غير محدود، ولا يغني عن مراجعة نموذج الوزن والـByzantine والـavailability.

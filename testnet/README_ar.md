# MOSAIC Testnet متعدد المضيفين

هذا الدليل يصف نشر testnet `mosaic-testnet-0` على سبعة validators مستقلين. ملف `hosts/inventory.example.json` هو inventory قابل للتعبئة، ولا يحتوي أسرارًا أو مفاتيح خاصة حقيقية. يجب استبدال أسماء المضيفين والمناطق والقيم الاقتصادية قبل التشغيل.

## حدود المرحلة الحالية

المشروع يملك daemon TCP وWAL وTLS اختياريًا وkey isolation، لكن testnet العامة الفعلية تحتاج مضيفين مستقلين أو Cloud Computer/third-party VMs مع عناوين قابلة للوصول، DNS أو عناوين ثابتة، firewall، ومشغّلين يملكون مفاتيحهم. لا يجوز اعتبار تشغيل سبع عمليات على `127.0.0.1` نشرًا متعدد المضيفين؛ ذلك يبقى local emulation.

## بوابة الاستعداد قبل التشغيل

قبل تشغيل أي عقدة، يجب أن يكون لكل validator مفتاح Ed25519 خاص لا يغادر المضيف، وشهادة mTLS صادرة من CA الخاصة بالtestnet، ومضيف مختلف فعليًا عن باقي validators، ووقت متزامن، ومسار WAL دائم، ونسخة احتياطية مشفرة، وفتح منفذ TCP الوحيد المطلوب. يجب تسجيل public key وstake bond وregion في genesis manifest، بينما تُرسل private key إلى مضيفها خارج Git وملفات التقارير.

| البوابة | معيار القبول |
|---|---|
| Identity | public key فريد لكل node، ولا يوجد private key في inventory أو repository |
| Network | كل pair من validators ينجح في mTLS handshake وframe exchange، مع timeout وrate limit |
| Storage | WAL وsnapshot وrestore ينجحان على disk مستقل بعد power-loss simulation |
| Membership | admission موقّع، minimum stake، withdrawal delay، وslash evidence قابلة للتدقيق |
| Beacon | commit/reveal round، fallback عند non-reveal، reward/penalty events، وتدوير اللجنة |
| Availability | نشر k+m shards، sampling proof، فقد provider، وrepair من providers آخرين |
| Observability | metrics محلية، event log append-only، incident ID، وupgrade event موثق |

## سجل الحوادث والترقيات

يجب أن يكتب كل validator أحداثًا JSONL append-only في `log_dir/events.jsonl`، وأن يحتوي كل حدث على `event_id` و`network_id` و`node_id` و`epoch` و`wall_time` و`software_version` و`config_digest` و`previous_event_hash`. أحداث crash وrestart وslashing وnon-reveal وrepair وcommittee rotation وupgrade لا تُحذف؛ ويُحفظ digest دوريًا خارج المضيف.

لا يُنفذ upgrade صامت. كل ترقية تحتاج `upgrade_id` ونسخة binary القديمة والجديدة وmigration digest ووقت البدء والنتيجة وقرار التراجع. أثناء testnet لا يُسمح بترقية consensus أو wire schema من دون إيقاف round أو وجود compatibility window مثبتة في manifest.

## الانتقال من local emulation إلى testnet فعلية

بعد تعبئة inventory وتشغيل مضيفين مستقلين، تُنفذ بوابة connectivity أولًا، ثم genesis onboarding، ثم stake settlement، ثم beacon round تجريبية، ثم availability round. لا يبدأ الحمل الطويل قبل نجاح هذه المراحل منفصلة. وفي غياب endpoints حقيقية أو اتصال SSH مع المضيفين، يمكن تنفيذ local multi-process rehearsal فقط، ويجب وسم نتائجه `LOCAL_EMULATION` في كل artifact.

> تصنيف الشبكة لا يرتفع إلى public testnet بمجرد أن تبدأ العمليات. يلزم أن ينضم validator مستقل فعليًا، وأن تظهر سجلاته ومفاتيحه وstake وavailability evidence في سجل قابل للتدقيق، وأن تبقى safety وliveness مقبولتين خلال فترة التشغيل المحددة.

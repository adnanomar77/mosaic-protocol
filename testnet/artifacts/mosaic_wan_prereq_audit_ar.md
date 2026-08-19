# MOSAIC WAN Testnet — تدقيق المتطلبات التشغيلية

**تاريخ التدقيق:** 2026-08-19  
**الحكم:** `BLOCKED — independent WAN hosts not supplied`  
**النطاق:** التحقق من إمكانية تعبئة inventory وتشغيل validators مستقلة من البيئة الحالية.

## النتيجة

البيئة الحالية هي sandbox واحدة باسم مضيف `87cd0e940adf`، وتملك واجهة `eth0` بعنوان داخلي link-local `169.254.0.21/30` وواجهة loopback `127.0.0.1`. لا توجد في المشروع endpoints أو inventory حقيقية؛ الموجود فقط هو `testnet/hosts/inventory.example.json` الذي يحتوي أسماء `example.net` وقيم `REPLACE_*`.

بناءً على ذلك، لا يمكن تصنيف تشغيل عدة daemons داخل هذه البيئة كـWAN testnet، ولا يجوز إنشاء شهادات ومفاتيح validators مستقلة بأسماء وهمية ثم اعتبارها هوية شبكة عامة. إنشاء private keys الحقيقية يجب أن يحدث على المضيف المخصص لكل validator، وأن تبقى المفاتيح خارج Git والتقارير وinventory العامة.

| المتطلب | نتيجة التدقيق | الحالة |
|---|---|---|
| سبعة مضيفين مستقلين | غير متوفرين في الجلسة الحالية | **BLOCKED** |
| عناوين WAN/DNS قابلة للوصول | غير متوفرة؛ العنوان الحالي link-local | **BLOCKED** |
| مشغلو validators مستقلون | لا توجد attestations أو بيانات مشغلين | **BLOCKED** |
| inventory حقيقية | الموجود قالب فقط مع `REPLACE_*` | **BLOCKED** |
| CA وشهادات mTLS | لا يمكن إصدار شهادات production قبل تثبيت hostnames وعناوينها | **PENDING** |
| private keys لكل validator | لم تُنشأ؛ وهذا صحيح أمنيًا قبل تحديد hosts | **PENDING** |
| firewall وفتح منفذ protocol | لا يمكن اختباره على WAN من sandbox الحالية | **BLOCKED** |
| disk دائم وbackup لكل node | لا توجد hosts هدف لتدقيقها | **PENDING** |

## ما يلزم لفتح البوابة

يجب توفير سبعة مضيفين مستقلين على الأقل، أو أربعة على الأقل لمرحلة connectivity أولية مع توضيح أن quorum النهائي يحتاج العدد المستهدف. يجب أن يملك كل مضيف مشغلًا أو حسابًا مستقلًا، وhostname أو public IP قابلًا للوصول، ومنطقة تشغيل، وSSH إداريًا مقيدًا، ومنفذ MOSAIC محددًا، ومسار disk دائم، ووقتًا متزامنًا، وسياسة backup.

يجب إرسال بيانات الاتصال العامة فقط في inventory: `node_id` و`host` و`port` و`region` و`operator_id` و`role` و`public_key` بعد توليده على المضيف. لا يجب إرسال private key أو سر CA عبر الدردشة أو Git. يمكن للمشغل تنفيذ bootstrap script على مضيفه أو استخدام قناة secrets آمنة.

## قرار المرحلة

لا تُنفذ مراحل key/certificate provisioning أو connectivity من هذه البيئة قبل وصول endpoints مستقلة حقيقية. سيبقى تصنيف MOSAIC كما هو: `Advanced Permissioned Reference Network / Pre-Public-Testnet`. بعد توفير البيانات العامة للمضيفين، تُستكمل المراحل بالترتيب: inventory validation، host-local key generation، CA/mTLS issuance، pairwise connectivity، onboarding، stake، beacon، availability، ثم WAN long-run وسجل الحوادث.

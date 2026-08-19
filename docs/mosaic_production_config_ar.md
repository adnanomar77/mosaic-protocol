# إعداد وتشغيل عقدة MOSAIC

يحتوي الملف `mosaic_node_config.example.json` على قالب عقدة حقيقي متوافق مع `python3 -m mosaic.daemon --config`. يجب إنشاء ملف مستقل لكل عقدة، مع الاحتفاظ بالمفتاح الخاص للعقدة على تلك العقدة فقط. لا يجوز نسخ `private_key_b64` إلى ملفات العقد الأخرى أو إلى مستودع عام.

## إنشاء مفاتيح المدققين

ينبغي توليد مفتاح Ed25519 مستقل لكل مدقق، ثم وضع المفتاح العام لجميع المدققين في كل ملف إعداد. يوضع المفتاح الخاص للمدقق المحلي في ملفه فقط، وتكون صلاحيات الملف والدليل مقيدة بحساب الخدمة، مثل `chmod 600 /etc/mosaic/node-w0.json` و`chmod 700 /var/lib/mosaic`.

```python
from base64 import b64encode
from ccd_nexus import KeyPair

key = KeyPair.generate()
print("public_key_b64:", b64encode(key.public_key).decode())
print("private_key_b64:", b64encode(key.private_bytes).decode())
```

يجب تنفيذ التوليد في بيئة موثوقة، وعدم إرسال المفاتيح الخاصة عبر الشبكة. قيمة `capability_hash` في `initial_seals` هي digest للقيمة المتفق عليها عند إنشاء المورد، ويجب أن تكون متطابقة في ملفات جميع العقد.

## تشغيل العقدة

بعد استبدال جميع الحقول الموسومة `REPLACE_` وتثبيت الشهادات، تشغّل العقدة بالأمر التالي:

```bash
cd /home/ubuntu/blockchain_alt
python3 -m mosaic.daemon --config /etc/mosaic/node-w0.json
```

يستخدم `DurableStore` قاعدة SQLite في `data_path` مع `journal_mode=WAL` و`synchronous=FULL`، ويستعيد الأختام والكبسولات والإيصالات والإغلاقات عند إعادة التشغيل. يجب وضع ملف البيانات على قرص دائم، وتضمين ملفات `*.sqlite`, `*.sqlite-wal`, و`*.sqlite-shm` في سياسة النسخ الاحتياطي أثناء نافذة checkpoint، مع إجراء `integrity_check` قبل اعتماد النسخة.

## TLS وmTLS

عند وجود قسم `tls` تصبح الاتصالات بين العقد TLS متبادلة التوثيق. يجب أن يحتوي `ca.crt` على سلطة الشهادات التي أصدرت شهادات جميع المدققين، وأن يتطابق كل `certfile` مع `keyfile` المحلي. لا تستخدم شهادات اختبار أو مفاتيح مشتركة في شبكة إنتاجية.

## حدود الجاهزية الحالية

القالب **قابل للتشغيل** لشبكة validators ثابتة ومصرّح بها، لكنه لا يضيف وحده اقتصاد Sybil permissionless، ولا آلة عقود ذكية عامة، ولا randomness لامركزيًا لاختيار اللجان. كما أن JSON framing والنموذج المرجعي الحالي مناسبان للتحقق والـdeployment الداخلي، ويجب استبدالهما أو تغليفهما ببروتوكول wire versioned ومحدد الحجم قبل فتح منفذ عام غير موثوق.

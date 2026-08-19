# MOSAIC Beacon Testnet Rehearsal

شُغلت أربع عمليات daemon مستقلة على المضيف المحلي، وكل عقدة بدأت من genesis admissions موقعة مع stake bonds ممولة من genesis balances. أُرسل لكل عقدة commit round عبر TCP إلى `w0`، ثم gossiped إلى باقي العقد، وكُشفت أسرار ثلاثة validators من أصل أربعة، ثم نُفذ `BEACON_FINALIZE` على `w0`.

النتيجة المحفوظة في `testnet/artifacts/mosaic_beacon_network_local.json` تثبت أن commit/reveal messages قُبلت، وأن `beacon_mode` كان `reveal`، وأن beacon proof وmembership root وsettlement root أُعيدت في response. سُجلت `beacon_round` وsettlement ledger في WAL. لم تظهر errors أو protocol rejections أو transport failures في metrics؛ وظهرت الرسائل المتكررة من gossip كـreplay-safe/idempotent state.

هذا rehearsal لا يساوي public testnet لأن العمليات الأربع تعمل على host واحد، ولا توجد committee rotation عبر حقب طويلة أو providers على hosts مستقلة. لكنه يغلق المسار البرمجي من genesis onboarding إلى beacon incentives، ويعطي بوابة قابلة لإعادة التشغيل قبل الانتقال إلى availability providers.

# MOSAIC Distributed Availability

أضيفت طبقة Reed-Solomon في `availability.py` مع `ErasureCodec(data_shards=k, parity_shards=m)`. تُجزأ البيانات إلى shards systematic وتُولد parity في GF(256)، ويمكن استعادة payload من أي `k` shards صحيحة من أصل `k+m`. كل shard يحمل `object_id` و`content_digest` و`shard_digest` ويُرفض إذا عُدّل.

أضيف `SamplingProof` لربط عينات shards بـindices وdigests وproof_id، وأضيف `AvailabilityStore` لنشر shards، استقبالها، فحص العينات، حساب missing indices، recovery، وrepair الحتمي للشards المفقودة. اختُبرت استعادة payload بعد فقدان shards، repair، sampling tampering، ورفض codec أو shard غير صحيح.

هذه خطوة فعلية نحو data availability، لكنها لا تعادل بعد شبكة availability عامة مكتملة. ما زال يلزم ربط كل provider بهوية validator ووزنه عبر `AvailabilityCertificate`، نشر shards عبر gossip أو worker network، retention policy، authenticated sampling عشوائي، repair scheduling، erasure-coded persistence، ومقاومة provider collusion وdata withholding على WAN.

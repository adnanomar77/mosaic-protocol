# MOSAIC Availability Provider Testnet Rehearsal

شُغلت خمس عمليات daemon مستقلة، وكل provider استخدم `ErasureCodec(k=3,m=2)` ومسار WAL منفصل. وُزعت shards الخمسة للـobject `network-object-0` عبر TCP على providers مختلفة. أُعيد جلب shards 0 و1 و2 من providers، وأُرسل source set إلى provider `w4` لتنفيذ repair للشards 3 و4، ثم أُجري sampling proof على الشards المُصلحة.

النتيجة في `testnet/artifacts/mosaic_availability_network_local.json` تثبت أن `recovered_payload_matches=true` و`restart_fetch_ok=true`. كما سجل provider `w4` `availability_repairs=1` و`availability_samples=1`، ولم تسجل العقد errors أو protocol rejections أو transport failures.

هذا يغلق المسار البرمجي من provider TCP إلى WAL وrepair، لكنه يظل `LOCAL_EMULATION`: كل العمليات على مضيف واحد، ولا يوجد بعد provider stake-weighted certificate أو authenticated random sampling عبر hosts فعلية أو data-withholding adversary على شبكة WAN. لذلك لا تُرفع الشبكة إلى public testnet بناءً على هذا rehearsal وحده.

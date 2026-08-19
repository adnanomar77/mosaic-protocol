# MOSAIC Protocol Specification v0.1

## Status and scope

هذه مواصفة بحثية قابلة للتنفيذ وليست معيارًا إنتاجيًا. لا تستخدم كلمة «نهائي» إلا عندما توجد `ClosureProof` صالحة، ولا تستخدم كلمة «آمن» خارج نموذج التهديد المحدد هنا.

## 1. Model and assumptions

يفترض البروتوكول لجنة موزونة ثابتة خلال epoch، ومجموع وزن `N`، ووزن Byzantine أقل من `N/3`. الرسائل قد تتأخر أو تتكرر أو تُرتب عشوائيًا أو تُحذف مؤقتًا. بعد نقطة `GST` تصبح الشبكة partially synchronous، وتستطيع العقد الصادقة التواصل خلال حد نهائي `Δ`. لا يعتمد safety على الساعة؛ تستخدم الساعة فقط لتفعيل abandonment بعد دليل زمني قابل للتحقق من اللجنة.

المهاجم يستطيع إنشاء رسائل ومفاتيح وتوقيعاته، لكنه لا يستطيع تزوير توقيع صادق أو كسر hash أو الحصول على وزن يتجاوز الفرضية. العضوية المفتوحة وSybil economics خارج v0.1؛ العضوية تأتي من `MembershipSnapshot` موقّع.

## 2. Canonical encoding

كل الرسائل تستخدم CBOR canonical أو JSON canonical في النموذج المرجعي، مع domain separation صريح:

```text
H(tag || version || epoch || fields...)
```

لا يسمح protocol بتوقيع serialization غير canonical. كل bytes موقعة تحفظ كما هي، ويعاد التحقق من digest قبل تحليل الحقول.

## 3. Wire objects

### 3.1 StateSeal

```text
StateSeal {
    resource_id: bytes32,
    epoch: u64,
    version: u64,
    state_root: bytes32,
    capability_hash: bytes32,
    owner: PublicKey,
}
```

### 3.2 Capsule

```text
Capsule {
    capsule_id: bytes32,
    predecessor: StateSeal,
    successor_root: bytes32,
    rule_id: bytes32,
    rule_witness: bytes,
    bundle_id: Option<bytes32>,
    attempt: u32,
    client_public_key: PublicKey,
    client_signature: Signature,
}
```

`capsule_id = H(CAPSULE_DOMAIN || canonical(CapsuleWithoutSignature))`. `attempt` جزء من digest ولا يُعاد استخدامه مع predecessor نفسه.

### 3.3 WitnessReceipt

```text
WitnessReceipt {
    capsule_id: bytes32,
    predecessor_id: bytes32,
    witness_id: PublicKey,
    epoch: u64,
    committee_seed: bytes32,
    status: ACCEPT | ABANDON,
    witness_signature: Signature,
}
```

لا يصدر witness `ACCEPT` لكبسولتين لهما predecessor نفسه. إذا ثبتت مخالفة محلية، تسجل العقدة evidence ولا تحاول ترجيح إحدى الكبسولتين.

### 3.4 ClosureProof

```text
ClosureProof {
    capsule_id: bytes32,
    predecessor_id: bytes32,
    epoch: u64,
    committee_seed: bytes32,
    signer_bitmap: bytes,
    aggregate_signature: Signature,
    weight: u128,
}
```

في v0.1 يحتفظ النموذج المرجعي بالتوقيعات الفردية بدل aggregate signature لتسهيل التدقيق. يجب أن يساوي `weight` مجموع الموقعين الفعليين، وأن يتجاوز `2N/3`.

### 3.5 ConflictEvidence

```text
ConflictEvidence {
    predecessor_id: bytes32,
    capsule_a: bytes32,
    capsule_b: bytes32,
    client_or_capability_signatures: tuple<Signature, Signature>,
}
```

الدليل لا يختار فرعًا. وظيفته إثبات أن مرشحَي successor لا يمكن إغلاقهما معًا أو أن مصدر capability خالف قاعدة الفرادة.

### 3.6 AbandonProof

```text
AbandonProof {
    predecessor_id: bytes32,
    capsule_id: bytes32,
    attempt: u32,
    epoch: u64,
    reason: TIMEOUT | INVALID | CLIENT_ABORT,
    signer_bitmap: bytes,
    aggregate_signature: Signature,
}
```

لا تُقبل `AbandonProof` إذا كانت `ClosureProof` للكبسولة نفسها موجودة لدى witness الموقع أو إذا وُجدت closure معتمدة في سجل epoch.

## 4. State machine

لكل predecessor حالة من الحالات التالية:

```text
AVAILABLE
  -> LOCKED(capsule_id, attempt)
  -> CLOSED(capsule_id)
  -> ABANDONED(capsule_id, attempt)
  -> LOCKED(new_capsule_id, attempt+1)
  -> CONFLICTED(evidence)
```

الانتقال إلى `CONFLICTED` لا يعني أن المورد ضاع؛ يعني أن محاولة الإغلاق الحالية تحتاج evidence أو abandonment حسب سياسة المورد. لا ينتقل المورد إلى `CLOSED` إلا عبر `ClosureProof`، ولا تُصرف outputs في `LOCKED` أو `ABANDONED`.

## 5. Algorithms

### 5.1 ValidateCapsule

```text
ValidateCapsule(C, local_state):
    check epoch and membership snapshot
    check predecessor equals current seal or a valid pending seal
    check client signature and capability_hash
    check deterministic rule_witness
    check successor version = predecessor.version + 1
    check bundle policy if bundle_id != None
    return VALID or INVALID(reason)
```

### 5.2 IssueReceipt

```text
IssueReceipt(C):
    if ValidateCapsule(C) == INVALID: reject
    key = (C.predecessor.id, C.epoch)
    if local_lock[key] is absent:
        local_lock[key] = (C.capsule_id, C.attempt)
        sign ACCEPT(C)
    else if local_lock[key] != (C.capsule_id, C.attempt):
        emit local ConflictEvidence
        do not sign C
    else:
        return idempotent existing receipt
```

### 5.3 Close

```text
Close(C):
    collect ACCEPT receipts matching predecessor, capsule, attempt, epoch
    if weighted_sum(receipts) > 2N/3:
        verify every signature and committee seed
        return ClosureProof(C)
    else:
        return PENDING
```

### 5.4 Abandon

```text
Abandon(C):
    require valid timeout/client-abort policy
    require no local knowledge of Closure(C)
    collect ABANDON receipts from >2N/3 weight
    return AbandonProof(C) or PENDING
```

### 5.5 Apply

```text
Apply(C, ClosureProof):
    require VerifyClosure(ClosureProof)
    require current_seal == C.predecessor
    install C.successor as current seal
    mark outputs spendable only if BundleClosure exists
    erase capability secret for predecessor
```

## 6. Safety arguments

### S1 — No two closures

لنفترض وجود إغلاقين مختلفين `D1` و`D2` من predecessor نفسه. كل واحد يملك وزنًا أكبر من `2N/3`. تقاطع مجموعتي الموقعين أكبر من `N/3`. وبما أن Byzantine weight أقل من `N/3`، يوجد witness صادق في التقاطع. قاعدة `IssueReceipt` تمنع witness الصادق من توقيع successor مختلف للـpredecessor نفسه. تناقض. إذن `¬(Closure(D1) ∧ Closure(D2))`.

### S2 — No apply without proof

التطبيق الوحيد يستدعي `VerifyClosure`، ويتحقق من predecessor الحالي ومطابقة digest. لذلك لا يمكن لرسالة عميل أو receipt جزئي أو certificate لمورد آخر نقل الحالة.

### S3 — No closure and abandon together

`AbandonProof` و`ClosureProof` يتطلبان عتبة أكبر من `2N/3` للـpredecessor/attempt نفسه. تقاطعهما يحوي witness صادقًا، وقاعدة الشاهد تمنع توقيع abandon إذا كان قد عرف closure صالحًا. لذلك لا يتعايش الدليلان تحت نموذج الأمان.

### S4 — Bundle atomic visibility

كل domain يحتفظ outputs كـ`PendingCapability`، ولا يجعلها spendable إلا بعد التحقق من `BundleClosure` الذي يحتوي closure لكل predecessor required وبنفس bundle digest. إذا غاب domain واحد، لا توجد قابلية صرف جزئية. هذا يثبت atomic visibility، لا atomic execution المجاني؛ قواعد التنفيذ يجب أن تكون deterministic وأن recovery policy تمنع تجميدًا دائمًا.

### S5 — Epoch separation

كل digest وشهادة يحتويان epoch وcommittee seed. لا تقبل عقدة receipt أو closure من snapshot قديم على حالة epoch جديد بلا `EpochTransitionProof`. هذا يمنع replay بين epochs.

## 7. Liveness obligations

السلامة لا تعتمد على GST، لكن liveness تعتمد على وصول الكبسولة إلى witness quorum بعد GST، وعلى أن اختيار الشهود لا يتركز في عقد متوقفة. يجب تحديد timeout قابل للمقارنة مع `Δ`، وأن يكون abandonment قابلًا للإصدار إذا لم توجد closure. إذا تعرضت اللجنة إلى أكثر من ثلث Byzantine أو انقطعت شبكة تمنع quorum، لا يعد البروتوكول بالتقدم.

## 8. Storage and garbage collection

يحتفظ المدقق الخفيف بـcurrent seal، وclosure proof، وmembership proof، وpending bundles ذات expiry. يمكن تقليم الكبسولات القديمة بعد حفظ checkpoint يثبت successor الحالي، لكن لا يجوز تقليم conflict evidence قبل انتهاء نافذة الاعتراض. يجب أن يكون checkpoint نفسه closure أو snapshot certificate مستقلاً.

## 9. Open proof obligations

قبل الادعاء بأن المواصفة كاملة إنتاجيًا، يجب إكمال: proof formal في TLA+/Ivy/Coq أو Lean؛ randomness/committee selection؛ cryptographic aggregation؛ reliable delivery أو availability؛ denial-of-service bounds؛ economic Sybil model؛ bundle recovery under crash; state-root authenticated storage؛ وقياس مستقل ضد baselines الرسمية.

## 10. Non-claims

MOSAIC v0.1 ليس permissionless blockchain، ولا يقدم smart-contract VM عامة، ولا يزيل الإجماع في التطبيقات التي تتطلب total order، ولا يضمن throughput أو latency قبل تشغيل network implementation حقيقي. الآلية المقترحة هي فرضية بروتوكولية محددة يمكن تدقيقها، لا إعلان ابتكار مثبت.

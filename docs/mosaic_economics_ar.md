# MOSAIC Economic Settlement

أضيف `SettlementLedger` لتسوية stake بدل إبقاء `StakeBond` ككائن إثبات منفصل فقط. يفرض ledger أن يكون bond ممولًا من رصيد المالك، ويقفل المبلغ أثناء النشاط، ويحول bond إلى unbonding عند طلب الخروج، ولا يسمح بالسحب قبل `unlock_epoch`.

يدعم ledger أيضًا تحصيل الرسوم من رصيد منفصل عن stake، تمويل treasury، توزيع مكافآت epoch بوزن bond، وعقوبة bond مع حصة reporter اختيارية. توجد حماية replay مستقلة لـslash evidence ومنع إعادة تسوية مكافآت epoch. يحسب ledger `state_root` ويحتوي `to_dict` و`persist` و`from_store` لاستعادة balances وbonds وevents بعد restart مع فحص state-root.

أصبح `MembershipManager` يقبل settlement اختياريًا. عند تفعيله، admission يتطلب bond ممولًا، وexit يطلب unbond من ledger، وwithdraw يعيد الرصيد بعد التأخير، وslash يخفض bond وstake معًا. بقيت واجهة العضوية القديمة متوافقة عندما لا يُمرر settlement.

> هذا ليس بعد نظام token permissionless كاملًا؛ لا يوجد في هذه المرحلة bridge إلى أصل خارجي أو custody موزع أو rewards market أو fee market على شبكة عامة. لكنه يزيل الفجوة بين إثبات stake محلي وتسوية اقتصادية قابلة للحفظ والتدقيق داخل عقد MOSAIC.

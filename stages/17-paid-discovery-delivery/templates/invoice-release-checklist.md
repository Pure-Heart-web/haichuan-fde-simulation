# Invoice Release Checklist

> Delivery 团队确认证据；只有授权财务可以创建发票、确认收入或登记回款。

- [ ] 合同和 PO/等效授权已在正式系统生效
- [ ] 里程碑及比例与合同一致
- [ ] 客户依赖对该里程碑的影响已处理
- [ ] 交付物按合同标准被授权验收人接受
- [ ] Change Order 已独立计价和批准
- [ ] 税、币种、发票主体和付款期限由财务确认
- [ ] 不存在阻断性争议、贷项或暂停条款
- [ ] Delivery/Commercial/Finance 职责分离

状态分别记录：`NOT_ELIGIBLE / ELIGIBLE / INVOICE_CREATED / SENT / DUE / PAID / DISPUTED / CREDITED`。代码生成的教学 `ELIGIBLE` 不得进入真实财务系统。

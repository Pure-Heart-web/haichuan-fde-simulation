# 外部 Deal Room 与证据处理

## 信息放置

| 信息 | 权威位置 | 仓库允许内容 |
|---|---|---|
| 客户法律名称、地址、税号 | CRM / Finance / Contract System | 不保存 |
| 联系人姓名、邮箱、电话 | CRM | 角色和不可逆引用 |
| MSA、SOW、DPA、签字页 | Contract System | 文档 ID、版本、状态、日期 |
| 安全问卷、架构和例外 | Security System | 工单 ID、决议、有效期 |
| PO、账单和银行信息 | Procurement / Finance | 记录 ID 和状态 |
| 数据样本和访问凭证 | 获批数据环境 / Secret Store | schema、分类和审批引用 |
| 商务活动 | CRM | opportunity/activity ID |

不要把真实合同、联系人、凭证、数据样本或签字页提交到 Git，也不要把它们复制到公开 issue、PR、CI log 或测试 fixture。

## Manifest 工作法

1. 在受控的仓库外目录运行 `stage18.py prepare`，或把生成的模板移动到受控位置；
2. 只填权威系统引用、角色、状态和日期；`public_label` 使用客户已允许展示的名称，否则使用内部代号；
3. 每项证据由非创建者或对应 Owner 核验，过期日期如实填写；
4. 运行 `preflight`，把结构缺口送回 Mutual Action Plan；
5. 结果为 Ready 后，由授权人员打开权威记录复核签字人、版本和法律效力；
6. Delivery Lead 完成人工 Release，并将 Stage 10 接入任务绑定到合同范围。

## 事故与撤销

若真实资料误入 Git，停止继续复制，立即通知 Security/Privacy Owner，撤销暴露的凭证，按公司流程清理历史和评估通知义务。仅删除当前文件不足以清除 Git 历史。合同被终止、证据过期或范围改变时，应撤销 Release，重新运行 preflight，并暂停依赖旧授权的工作。

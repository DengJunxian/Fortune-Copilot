# 设计来源锁

锁定时间：2026-08-04（Asia/Shanghai）

| 来源 | 实际 HEAD | 许可证 | 实际读取文件 | 用途 | 获取与降级状态 |
| --- | --- | --- | --- | --- | --- |
| VoltAgent/awesome-design-md | 8147538b4226ae41e2487a9179e3bcc1f68e8554 | MIT，Copyright 2026 VoltAgent | references/design-md/ibm/DESIGN.md；revolut/DESIGN.md；linear.app/DESIGN.md；references/UPSTREAM_LICENSE | 企业信息秩序、消费者金融表达、高密度产品层级研究 | git ls-remote 在线核验 HEAD；读取本机固定 SHA 快照；不进入运行时 |
| Leonxlnx/taste-skill | e988add20dab0fa97d7a76781c48961c8184288e | MIT，Copyright 2026 Leonxlnx | skills/redesign-skill/SKILL.md；skills/taste-skill/SKILL.md；LICENSE | Scan/Diagnose/Fix 审计、brief inference、反模板和 pre-flight | npx skills add 成功安装到 .agents/skills；skills-lock.json 记录哈希；不进入运行时 |

## 版本核验

- 两个仓库均通过 git ls-remote 在锁定日核验实际 HEAD，结果与提示词基线一致。
- awesome-design-md 本地技能声明相同 commit，IBM、Revolut、Linear 文件已完整阅读。
- taste-skill 先出现克隆进度输出不完整，随后两个指定技能均成功写入项目 .agents/skills，skills-lock.json 可复核 source、skillPath 和 computedHash。

## 使用边界

- 不复制商标、Logo、专有字体、品牌插画、完整色板或页面结构。
- 外部文件不被前端打包，不是 npm 或运行时依赖。
- 现场无网络时使用仓库 DESIGN.md、tokens.css 和本文档继续运行。
- 若将来上游 HEAD 变化，必须显式重新审计并更新此锁文件，禁止静默跟随 main。


# 架构取舍之道：从 Redis、MySQL、Kafka 理解系统设计

> 一个架构师对 Redis / MySQL / Kafka 设计共性的十年观察笔记。三个软件是观察样本，真正的主题是观察方法本身。

**在线阅读：** <https://jgsliu7.github.io/architecture-tradeoffs/>

## 关于本书

多年来，我们一直在用 Redis、MySQL、Kafka 这三款软件。大多数资料教的是用法、配置、调优，却很少有人从架构的视角去寻找它们的共性。

这三款都是优秀的软件，但它们解决的问题多有相通之处：

- 如何优雅地启动与关闭？（数据存储类软件不能像断电那样粗暴地停）
- 内存与磁盘的关系如何处理？（要快就得用内存，可内存与磁盘怎么协同？）
- 分层架构如何设计？（存储层、逻辑层、交互层之间的职责划分）
- 安全如何保障？
- 集群如何构建？
- 磁盘文件格式如何设计？（三家各有妙法）
- 集群之间数据如何同步？

万法归一，本质上都是特性的取舍。写这本书，是想透过现象看本质，从架构的高度去理解软件设计之道：不把这三款当成孤立的工具，而当成对同一组问题的三次不同回答。

## 目录

| 章节 | 标题 | 正文 |
|------|------|------|
| 序言 | 序言 | [阅读](chapters/00-preface.md) |
| 第 1 章 | 引言 — 为什么是这三个软件 | [阅读](chapters/01-introduction/chapter.md) |
| 第 2 章 | 数据结构与协议 — 为各自的目标而设计 | [阅读](chapters/02-data-structures-protocols/chapter.md) |
| 第 3 章 | 生命周期管理 — 优雅启动与关闭 | [阅读](chapters/03-lifecycle/chapter.md) |
| 第 4 章 | 内存与磁盘 — 速度与持久化的平衡 | [阅读](chapters/04-memory-disk/chapter.md) |
| 第 5 章 | 分层架构设计 — 存储层 / 逻辑层 / 交互层 | [阅读](chapters/05-layered-architecture/chapter.md) |
| 第 6 章 | 安全机制 — 权限、加密、审计 | [阅读](chapters/06-security/chapter.md) |
| 第 7 章 | 集群架构 — 从单点到分布式 | [阅读](chapters/07-cluster/chapter.md) |
| 第 8 章 | 磁盘存储格式 — 文件结构的设计哲学 | [阅读](chapters/08-storage-format/chapter.md) |
| 第 9 章 | 数据同步机制 — 集群一致性的实现 | [阅读](chapters/09-data-sync/chapter.md) |
| 第 10 章 | 总结：架构设计的共性规律与取舍 | [阅读](chapters/10-summary/chapter.md) |
| 后记 | 后记 | [阅读](chapters/10-epilogue.md) |

## 版本约定

本书分析基于以下软件版本：

| 软件 | 版本 | 说明 |
|------|------|------|
| **Redis** | 7.x | 包含多线程 I/O、ACL、Function 等机制 |
| **MySQL** | 8.0.x | 以 InnoDB 为主要讨论对象 |
| **Kafka** | 3.x | 讨论 KRaft 元数据管理；Tiered Storage 相关讨论以 3.9+ 为准 |

具体讨论范围、版本差异与信息核对日期见[第 1 章的版本基线与阅读约定](chapters/01-introduction/chapter.md)。

## 本地构建

需要 Python 3.10+，无第三方依赖。

```bash
python3 scripts/build_pages.py
```

产物为 `dist/index.html` 与 `dist/chapters/*.html`。每章页面已内联 SVG 图示，可离线浏览。

公开版构建时设置 `BOOK_EDITION=public`，页面会显示“在线阅读版”；不设置则保留内部审阅使用的“分页审阅版”称谓。

## 仓库说明

这个仓库只保留成书核心：正文、插图、构建脚本和构建后的网页。写作过程中的大纲、审校记录、历史版本和中间稿不在这里。

## 勘误与反馈

欢迎通过 [Issues](https://github.com/jgsliu7/architecture-tradeoffs/issues) 提交勘误。技术细节随版本演进，采纳前请以 Redis、MySQL、Kafka 官方文档为准。

## 许可证

- **正文与插图**：CC BY-NC-ND 4.0。可免费阅读、原样转载，不得用于商业目的，不得分发改编作品。见 [LICENSE](LICENSE)。
- **构建脚本**：MIT。见 [LICENSE-CODE](LICENSE-CODE)。

## 商标与免责声明

Redis 是 Redis Ltd. 的商标；MySQL 是 Oracle Corporation 及其关联公司的商标或注册商标；Apache Kafka、Kafka 是 Apache Software Foundation 的商标。本书对上述名称的使用仅作技术讨论，不代表各商标权属方对本书内容的认可。

本书所含信息仅供学习与参考。作者不对因采纳本书中的任何技术建议、配置参数或架构方案而导致的任何直接或间接损失承担责任。书中提及的第三方软件与服务的性能、安全性与可用性以其官方文档为准。

## AI 辅助说明

本书的初稿与文字打磨借助了生成式 AI 工具。书中的假设场景用于解释机制与取舍，所有技术判断、取舍与案例均由作者独立负责；残留的错漏由作者负责。详见[后记](chapters/10-epilogue.md)。

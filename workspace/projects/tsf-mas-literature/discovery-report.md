# 时间序列预测与多智能体协同：初步文献发现

检索日期：2026-10-29（Asia/Shanghai）。阶段：发现与初筛；非系统综述，未开展全文深度阅读。用户确认三篇后才进入阅读。公开检索词，不涉及私人材料。

## 执行和证据边界

项目 `.codex/agents/literature_search.toml` 确实存在；本次原生 `spawn_agent` 接口没有选择角色类型的参数，也没有可验证的该配置角色调用事件。因此 **已配置的 literature_search 未能实际调用／验证，状态 blocked**。两个真实运行的通用协作子代理分别执行 A、B 检索，它们不是该已配置角色。Citation 和 Reading 角色均未调用。主控独立核查关键来源并汇总。没有写入 Zotero 或 Obsidian。

项目独立 Python CLI 曾按公开主题尝试 Crossref 和 arXiv，但网络或超时错误，0 条返回；它不是 LLM，也不会启动配置角色。原始日志见 `search-cli/`，不要把该次失败误称为完成的数据库检索。随后通过可用网页检索与来源页面进行发现和核验。部分网络抓取由搜索索引呈现，不代表直接获取全文。已验证论文身份与关联，不表示已完成系统性引用核验、复现、同行评审质量评价或用户认可。所有论文均未深读；能打开全文不代表读完。

## 范围和可复查策略

- B 优先：时间序列或其他未来量的预测，具体进入多主体的规划、决策、调度或资源协调。A：多个角色通过信息交换、融合或协作来生成预测。边界项明确标注，不将“预测”和“控制”并列就视为预测值确实输入控制器。
- 优先英文 2024–2026 期刊、会议和高相关 arXiv；少量 2023 在线／2024 卷刊作为区块链架构参照。纳入依据是预测—决策数据流、协作机制和可核验来源，而非年份、平台或引用量。排除仅单一代理、单纯预测且无明确协作、只做资源调度而未证实预测的条目。初筛允许摘要／元数据可见但全文未获取。
- 逻辑式（按来源语法改写）：`("time series forecasting" OR "demand forecasting" OR "load prediction" OR "traffic prediction") AND ("multi-agent" OR "multi agent reinforcement learning" OR MAS) AND (coordination OR scheduling OR "resource allocation")`；A 增加 `communication topology`, `message passing`, `collaboration`, `voting`；区块链增加 `blockchain`, `smart contract`, `energy trading`, `federated learning`。
- 主控网页实际查询包括：`"forecasting" "multi-agent" coordination scheduling prediction demand multi agent reinforcement learning`；`"time series forecasting" "multi-agent" collaboration communication forecasting 2025`；`multi agent reinforcement learning demand forecasting resource allocation 2024 forecasting`；`"forecast" "multi agent" reinforcement learning demand scheduling forecasting 2025`；`"multi-agent" "forecasting" "coordination" energy demand reinforcement 2024`；`"Many Minds, One Goal" "Sub-task Specialization" NeurIPS 2025`；以及针对标题的核验查询。协作子代理的逐条查询记录未完整保留，故本次不能完整重放其所有发现。
- 实际核验来源：NeurIPS 官方论文集、arXiv、Springer/Nature、Frontiers、作者机构保存稿、IEEE 机构保存稿及出版社索引；部分 Elsevier 直接页面 403。未对 ICML、ICLR、AAAI 官方库做完整遍历，不能据此声称无相关论文。检索引擎返回排序和总量不可稳定复现，缺少统一检索总数；未进行 PRISMA 流程或全文筛选。以 DOI、标题及作者识别重复；下列 13 条是人工去重后候选，未追溯全部被排除记录。A 类或能源场景偏多，反映有限检索覆盖，不代表领域构成。
- 阅读证据记号：`摘要`＝论文摘要已检查；`正文定位`＝仅点查指定段落、图表或作者版摘要；`全文可用`＝链接或页面可见，不表示已阅读全部内容；`索引`＝搜索索引提供摘要／片段，页面直接访问失败。相关性是与问题的契合度，不是研究质量评级。

## 候选文献（13 篇）

### B：预测辅助协同、调度及资源协调

1. **[Dynamic scheduling of flexible bus services with hybrid requests and fairness: Heuristics-guided multi-agent reinforcement learning with imitation learning](https://doi.org/10.1016/j.trb.2024.103069)** — Weitiao Wu, Yanchen Zhu, Ronghui Liu；*Transportation Research Part B*, 190, 103069，2024，正式期刊。**高**。预测历史需求和纠正预测误差，结合多智能体强化学习、局部搜索和模仿学习，联合决策车辆路线、时刻与乘客分配；作者报告数值实验和广州案例。证据：摘要与[作者接受稿](https://eprints.whiterose.ac.uk/id/eprint/218754/1/DRT-RL-accept%20-%20Sept2024.pdf)第 2、6–7 页点查；全文可用，未深读。适合研究预测误差如何影响协同调度；具体预测模型和基线仍待核查。

2. **[MASSIVE: A scalable framework for agent-based scheduling of micro-grids using market mechanisms](https://doi.org/10.1186/s42162-025-00558-w)** — Jakob M. Fritz, Lea Riebesel, André Xhonneux, Dirk Müller；*Energy Informatics* 8, 101，2025-07-28，正式期刊。**高**。Agent 各自预测供需，借助价格和滚动市场出清协调；市场出清为集中优化，参与者为分布式 Agent。证据：出版社摘要和 Appendix A、仿真假设定位，开放全文可用。示例光伏场景采用完美预测，摘要声称滚动机制减轻误差敏感性，但不能据此认定误差鲁棒性已在该场景得到验证。

3. **[Optimized multi agent reinforcement learning algorithms with hybrid BiLSTM for cost efficient EV charging scheduling](https://doi.org/10.3389/frai.2025.1700664)** — Urvashi Khekare, Rajay Vedaraj I. S.；*Frontiers in Artificial Intelligence*，2026-01-05 发表，卷标 2025，正式期刊。**高**。POA 调参 BiLSTM 预测电价和需求，再输入集中训练、分散执行的多 Agent 充电调度；有预测方法影响调度的表格。证据：摘要及 Algorithm 1、Table 3 的点查；全文开放。表格与正文部分误差数字不一致，暂不采信精确改进幅度，需后续核验。

4. **[MaRCA: Multi-Agent Reinforcement Learning for Dynamic Computation Allocation in Large-Scale Recommender Systems](https://arxiv.org/abs/2512.24325)** — Wan Jiang, Xinyi Zang, Yudong Zhao, Yusi Zou, Yunfei Lu, Junbo Tong, Yang Liu, Ming Li, Jiani Shi, Xin Yang；2025-12-30，arXiv 预印本 v1，未核实正式发表。**高**。以推荐系统多个阶段为协作 Agent，集中训练／分散执行；MPC 流量预测调整收益—算力权衡。作者摘要报告线上应用，但部署效果尚未独立验证。证据：arXiv 元数据、摘要；PDF/HTML 链接可用，未深读。流量预测的具体建模和与 Agent 交互接口需继续核验。

5. **[Edge-driven resource allocation in vehicular networks: A joint framework of multi-agent reinforcement learning and demand-supply predictive modeling](https://doi.org/10.1016/j.rineng.2025.106100)** — Dhinesh Kumar R, Rammohan A；*Results in Engineering* 27，2025，正式期刊。**高**。检索到的摘要／方法片段描述 LSTM 预测网络状态，邻近路侧单元共享资源池，多 Agent PPO 与 DDPG 分别处理频段和功率分配；不同道路场景仿真。证据：出版社索引摘要及方法片段，直接页面 403；未验证全文，拓扑细节与实验待查。

6. **[Governance-aware autonomous retail coordination in artificial intelligence cities using multi-agent reinforcement learning, blockchain accountability, and federated learning](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1942376/full)** — Toqeer Ali Syed, Ali Akarma, Shahid Kamal, Salman Jan, Ahmad B. Alkhodre, Arshad Jamal；*Frontiers in Artificial Intelligence* 9，2026-10-07，正式期刊，DOI [10.3389/frai.2026.1942376](https://doi.org/10.3389/frai.2026.1942376)。**高**。需求预测向订货策略提供预测向量及不确定性，结合多角色协调、联邦学习与许可链责任记录。证据：摘要、§3.2.1–3.2.4、实验表题；开放全文可用，未深读。文章列有模拟、M5 数据和链测试床；尚未验证消融、链的必要性和安全声明。

7. **[A blockchain-enabled multi-agent deep reinforcement learning framework for real-time demand response in renewable energy grids](https://doi.org/10.1016/j.esr.2025.101905)** — Arvind R. Singh, R. Seshu Kumar, Mohit Bajaj, B. Hemanth Kumar, Vojtech Blazek, Lukas Prokop；*Energy Strategy Reviews* 62, 101905，2025，正式期刊。**高，但需谨慎核验**。GridSyncNet 结合负荷预测、多 Agent 强化学习与区块链交易／协调。证据：出版社搜索索引的摘要及部分正文，直接访问 403；作者顺序由独立条目核对，仍需与正式版对照。索引中的预测准确率 92.4% 与摘要所述 97.4% 不一致，不能作为确定结论；链设计、数据和结果均待全文核查。

8. **[Multi-modal and multi-agent reinforcement learning framework for urban traffic flow prediction and signal control optimization](https://www.nature.com/articles/s41598-026-37722-5)** — Ruokun Wang, Ju Zhang, Xikui Wang, Haoyang He, Yuelin Zou；*Scientific Reports* 16, 7612，2026-02-06，正式期刊，DOI [10.1038/s41598-026-37722-5](https://doi.org/10.1038/s41598-026-37722-5)。**中，边界项**。时空图网络提取交通特征，多 Agent 控制多路口信号；预测头与控制共享表示。证据：摘要、方法片段，全文可用；尚未证明预测输出本身输入决策，因而不视为已确证的 B 核心例证。

### 区块链架构参照（B 邻近）

9. **[Integrating Forecasting Service and Gen2 Blockchain Into a Local Energy Trading Platform to Promote Sustainability Goals](https://doi.org/10.1109/ACCESS.2023.3347432)** — Liaqat Ali, M. Imran Azim, Nabin Babu Ojha, Jan Peters, Vivek Bhandari, Anand Menon, Jemma Green, S. M. Muyeen；*IEEE Access* 12, 2941–2964，2023-12-25 在线发表、2024 卷刊，正式期刊。**中至高，预测与链的参照**。将负荷、光伏和电池状态预测服务与本地 P2P 能源交易、第二代链及二层扩容结合；不能仅据摘要断言其为学习型多 Agent 协作。证据：[机构书目和摘要](https://research.monash.edu/en/publications/integrating-forecasting-service-and-gen2-blockchain-into-a-local-)及[机构保存稿](https://qspace.qu.edu.qa/bitstream/handle/10576/62132/Integrating_Forecasting_Service_and_Gen2_Blockchain_Into_a_Local_Energy_Trading_Platform_to_Promote_Sustainability_Goals.pdf?isAllowed=y&sequence=1)的索引首页；直接 PDF 访问曾受限，未深读。作者与平台公司有关，利益关系需后续查证。

### A：多 Agent 协作改进时间序列预测

10. **[Many Minds, One Goal: Time Series Forecasting via Sub-task Specialization and Inter-agent Cooperation](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f34f0630c33be15b8c89426bb8056798-Abstract-Conference.html)** — Qihe Huang, Zhengyang Zhou, Yangze Li, Kuo Yang, Binwu Wang, Yang Wang；NeurIPS 2025 主会论文，DOI [10.52202/085713-5550](https://doi.org/10.52202/085713-5550)。**高**。MAFS 将任务拆成不同时间尺度或信号子任务，通过 Agent 信息交换和投票融合预测；作者报告 11 个基准。官方摘要及[作者代码说明](https://github.com/h505023992/MAFS)可见，后者描述环、星、链、全连接及可学习权重；全文 PDF 可用但未深读，尚未复核具体消融与公平性。

11. **[Visual Reasoning over Time Series via Multi-Agent System](https://arxiv.org/abs/2602.03026)** — Weilin Ruan, Yuxuan Liang；2026-02-03，arXiv 预印本 v1，未核实正式发表。**高（A 通信）**。Analyzer、Reasoner、Executor 通过共享记忆和门控通信协作，路由器选择工具链；使用视觉推理与轨迹重建。证据：arXiv 摘要，PDF/HTML 链接可用；未深读，不推断其应用于 B 协调决策。

12. **[Can Competition Enhance the Proficiency of Agents Powered by Large Language Models in the Realm of News-driven Time Series Forecasting?](https://arxiv.org/abs/2504.10210)** — Yuxuan Zhang, Yangyang Feng, Daifeng Li, Kexin Zhang, Junlan Chen, Bowen Deng；2025-04-14，arXiv 预印本 v1，未核实正式发表。**中至高（A 交互机制）**。将竞争引入多 Agent 讨论，并用微调小模型辅助反思／识别误导；作者摘要报告预测改善。证据：arXiv 摘要；全文链接可用，未深读。竞争强度和结果可重复性待核查。

13. **[TimeSeriesScientist: A General-Purpose AI Agent for Time Series Analysis](https://arxiv.org/abs/2510.01538)** — Haokun Zhao, Xiang Zhang, Jiaqi Wei, Yiwei Xu, Yuting He, Siqi Sun, Chenyu You；2025-10-02 v1、2025-10-06 v2，arXiv 预印本，未核实正式发表。**中（A 架构）**。Curator、Planner、Forecaster、Reporter 分工处理诊断、建模、预测与报告；8 个基准为作者摘要声明。证据：arXiv 元数据和摘要，全文链接可用；这是角色流水线，不能据此断言存在充分验证的去中心化协作。

## 精选三篇与互补性

| 推荐 | 方向／问题 | 输入与协作方式 | 可读证据和下一步 |
|---|---|---|---|
| Wu 等 2024 | B：预测误差下的车辆与乘客调度 | 历史需求预测、误差修正 + MARL、局部搜索、模仿学习 | 作者接受稿及摘要可见；优先核对预测方法、基线、误差实验与动作信息流 |
| Fritz 等 2025，MASSIVE | B：分布式参与者如何通过市场协调 | 各 Agent 预测供需，集中市场出清、价格信号与滚动调整 | 开放全文；优先检查消息、规模与预测假设；示例使用完美预测 |
| Huang 等 2025，MAFS | A：通信和子任务分工能否改善预测 | 时间视角专门 Agent、消息拓扑、投票融合 | NeurIPS 正式论文及代码可用；核验拓扑、通信消融及匹配计算预算基线 |

**理由：** Wu 最直接地回答预测如何作用于实际分配，并显式触及预测错误和多目标调度；MASSIVE 提供与 MARL 不同的市场协调架构和扩展性考量，适合提出预测—价格—行动接口问题，但完美预测示例限制了误差结论；MAFS 直接提供通信拓扑、预测专门化和融合的实验设计，可为 B 的信息共享机制提供灵感，但它本身主要是 A。三篇依次覆盖决策效果、协作架构与预测端通信机制，并不宣称互相证明效果或覆盖整个领域。若区块链是第一优先，可在确认时用 Syed 等 2026 替换其中一篇。

## 区块链的可能位置与待验证问题

Syed 等和 Singh 等的候选说明有人提出将预测、Agent 和链组合；Ali 等提供交易基础设施参照。这只能证明相关设计存在，并不证明区块链必需或一定提升安全与性能。可探索的角色包括：对预测版本、资源承诺和决策记录做可验证审计；通过智能合约结算／执行多方约定；保留链下预测及实时控制、在适当粒度上链。实际效益需与中心化数据库、签名日志或无链协调基线比较，衡量隐私、吞吐、确认延迟、费用、参与方信任与故障恢复。

以下是待检验问题，不是已证实的领域空白：

1. 点预测、分位数与校准的不确定性，分别如何改变多 Agent 的成本、服务公平性及约束违约？比低预测误差更重要的是否是决策损失？
2. 在相同训练和通信预算下，环、星、邻域图、全连接、动态拓扑与市场广播对预测质量、任务成功率和可扩展性的影响如何？
3. 局部预测误差、缺失数据、时延、策略非平稳和分布漂移如何传播到其他 Agent？何时应降低通信、重新规划或回退安全策略？
4. 集中训练／分散执行、市场出清和层次化分配在相同信息与计算条件下，何者更适合约束和异构目标？
5. 能否把 A 的协作预测和 B 的决策闭环联合优化，而不发生数据泄漏、训练—部署不一致或对未来信息的误用？
6. 跨机构多主体是否真的需要链？链下实时控制与链上审计如何分工，和签名日志比较是否仍有净收益？

本轮没有评估上述问题的领域新颖性；需要扩大数据库、追溯引用和逐篇阅读后再判断。

# YAML 配置详细说明 — 以 `action` 为核心

## 一、配置层级总览

```
config.yaml                 ← 全局设置 + defaults 默认值 + active_flow
    │
    └── flows/<流程名>.yaml ← 一个流程 = loop_count + steps[]
            │
            └── steps[]     ← 每个元素是一个 step
                    │
                    └── action  ← ★ 核心：决定这个 step 干什么
                            └── 该 action 专属的参数
```

**一句话理解**：
> `action` 是"动词"，其他字段是"宾语和状语"。**先看 action，再查该 action 支持哪些字段。**

---

## 二、`action` 的分类（按功能）

| 分类 | action | 作用 |
|------|--------|------|
| **点击类** | `click` | 点击坐标 |
| | `find` | OCR 查找文本，记录坐标 |
| | `find_click` | 查找并点击 |
| | `poll_click` | 反复点击直到页面变化 |
| **等待类** | `wait` | 纯等待 |
| | `wait_text` | 等待文本出现 |
| **循环类** | `repeat` | 次数循环 |
| | `for_each_coord` | 遍历坐标列表 + 内循环 |
| **控制类** | `abort_check` | 条件检查 / 终止 |
| | `call_flow` | 调用子流程 |
| **扩展类** | `run_method` | 调用 Python 方法 |
| **调试类** | `dump_ocr` | 打印当前页面 OCR |

---

## 三、通用字段（所有 action 都可用）

写在 step 顶层，与 `action` 平级：

```yaml
- action: click
  # ↓↓↓ 通用字段 ↓↓↓
  remark: "日志说明"       # 打印在日志里，方便排查
  enabled: true            # false 则跳过本步
  sleep: 0.5               # 本步执行后休眠（秒）
  before: [...]            # 前置子步骤（本 action 执行前）
  after: [...]             # 后置子步骤（本 action 执行后）
  expect_text: "..."       # 期望出现的页面关键词（用于页面校验）
  # ↓↓↓ 查找类通用字段 ↓↓↓
  text: "目标文本"          # OCR 目标（find / find_click / wait_text 用）
  exact: true              # 是否精确匹配
  retry: 3                 # OCR 重试次数
  retry_interval: 1.0      # 重试间隔（秒）
  interval: 0.5            # 通用间隔（点击间隔 / 循环间隔）
  optional: false          # 找不到时是否跳过（不报错）
  region: [x1, y1, x2, y2] # 限定查找区域（绝对坐标）
  region_size: 300         # 以 coords 为中心的矩形边长
  region_w: 300            # 以 coords 为中心的矩形宽
  region_h: 300            # 以 coords 为中心的矩形高
```

**默认值来源**：
- 未写的字段 → 从 `config.yaml` 的 `defaults` 取。
- `defaults` 里也没有 → 代码里的硬编码默认值。

---

## 四、每个 action 的详细配置方法

---

### 1. `click` — 点击

**作用**：点击一个坐标（固定坐标、上次查找结果、或当前遍历坐标）。

**参数**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `target` | 否 | `coords`（用本步 coords）/ `last`（用上次 find 的坐标）/ `skill`（同 last）。默认 `last` |
| `coords` | target=coords 时必填 | `[x, y]` |
| `times` | 否 | 点击次数，默认 1 |
| `interval` | 否 | 多次点击之间的间隔，默认取 defaults |
| `sleep` | 否 | 本步后休眠 |
| `expect_text` | 否 | 点击前先校验页面 |

**示例**：

```yaml
# ① 固定坐标点一次
- action: click
  remark: "点击确定"
  target: coords
  coords: [553, 2257]
  times: 1
  sleep: 0.5

# ② 连点 60 次
- action: click
  remark: "领悟 ×60"
  target: coords
  coords: [772, 2282]
  times: 60
  interval: 0.2

# ③ 点击上次 find 找到的坐标
- action: find
  text: "升级"
- action: click
  remark: "点击刚找到的升级按钮"
  target: last
  times: 1

# ④ 点击当前 for_each_coord 遍历到的坐标
- action: for_each_coord
  coords_list: [[389, 1328], [895, 1313]]
  steps:
    - action: click
      target: last      # 就是当前坐标项
      times: 1
```

**注意**：
- `target: last` 依赖上一次 `find` / `for_each_coord` 记录的 `last_coord`。
- 如果 `last_coord` 为空且 `optional: true`，会跳过点击继续下一步。
- `text` 字段对 `click` **只是日志**，不参与查找。

---

### 2. `find` — OCR 查找（记录坐标，不点击）

**作用**：截屏 OCR，找到文本后把中心坐标记到 `last_coord`，供后续 `click target=last` 使用。

**参数**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `text` | 是 | 要查找的文本 |
| `exact` | 否 | 是否精确匹配，默认取 defaults |
| `expect_text` | 否 | 页面校验关键词（字符串/列表/规则字典） |
| `region` / `region_size` / `region_w` / `region_h` | 否 | 限定查找区域 |
| `retry` | 否 | 重试次数 |
| `retry_interval` | 否 | 重试间隔 |
| `optional` | 否 | 找不到是否跳过 |

**示例**：

```yaml
- action: find
  remark: "查找升级按钮"
  text: "升级"
  exact: false
  region: [400, 2000, 700, 2400]
  retry: 3
  retry_interval: 0.5

- action: click
  target: last      # 点击刚找到的坐标
```

**`expect_text` 三种写法**：

```yaml
# ① 字符串
expect_text: "建造"

# ② 列表（OR，任一命中）
expect_text: ["建造", "研究", "升级"]

# ③ 规则字典
expect_text:
  mode: mixed          # and | or | mixed
  match_mode: all      # all | any（仅 mixed 有效）
  rules:
    - type: must       # must(全部出现) | any(任一出现) | not(全部不出现)
      keywords: ["建造"]
    - type: not
      keywords: ["取消"]
```

---

### 3. `find_click` — 查找并点击

**作用**：`find` + `click` 的组合。找到文本后点击它。

**参数**：同 `find`，外加：

| 字段 | 说明 |
|------|------|
| `target` | 若为 `coords`，则点击本步 `coords`；否则点击找到的坐标 |

**示例**：

```yaml
# ① 查找并点击找到的坐标
- action: find_click
  text: "升级"
  expect_text: "建造"
  times: 2
  interval: 0.5
  sleep: 0.5

# ② 查找文本存在，但点击固定坐标
- action: find_click
  text: "进阶"
  exact: false
  target: coords
  coords: [540, 2277]
  region_size: 300
  retry: 4
  retry_interval: 0.2
  optional: true          # 进阶没出现就跳过
```

**典型场景**：`find_click` 用于"按钮位置会变，但需要先确认它出现"的场景。`optional: true` 让它变成"可选点击"。

---

### 4. `poll_click` — 轮询点击直到页面变化

**作用**：反复点击同一坐标（或坐标列表），直到 `expect_text` 消失或达到 `times`。

**参数**：

| 字段 | 说明 |
|------|------|
| `coords` | 单个坐标 |
| `coords_list` | 坐标列表 |
| `expect_text` | 期望出现的页面文本（默认 "升级"） |
| `click_text` | 点击文本（默认 "升级"） |
| `times` | 最大轮询次数 |
| `interval` | 每轮间隔 |
| `start_text` / `end_text` | 自动推算 2×2 坐标（兼容旧算法） |

**示例**：

```yaml
- action: poll_click
  remark: "轮询点升级直到页面关闭"
  coords_list:
    - [389, 1328]
    - [895, 1313]
    - [375, 1500]
    - [893, 1495]
  expect_text: "升级"
  click_text: "升级"
  times: 20
  interval: 1.0
```

**执行逻辑**：
1. 点击坐标 → 等页面打开。
2. 若 `expect_text` 出现 → 找 `click_text` 并点击 → 等页面关闭。
3. 若页面没打开（已满级）→ 标记该坐标完成，换下一个。
4. 每个坐标最多轮询 `times` 次。

---

### 5. `wait` — 纯等待

**作用**：等待指定秒数。等待过程中会响应异步 abort 命中。

**参数**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `seconds` | 是 | 等待秒数 |

**示例**：

```yaml
- action: wait
  seconds: 1.0
```

**注意**：`wait` 内部按 0.2s 切片，每片检查一次异步 abort，所以能被打断。

---

### 6. `wait_text` — 等待文本出现

**作用**：反复 OCR 直到文本出现，或重试耗尽。

**参数**：

| 字段 | 说明 |
|------|------|
| `text` | 等待的文本 |
| `exact` | 是否精确匹配 |
| `retry` | 重试次数 |
| `retry_interval` | 重试间隔 |
| `region` 等 | 限定区域 |
| `optional` | 超时是否跳过 |

**示例**：

```yaml
- action: wait_text
  remark: "等确定按钮出现"
  text: "确定"
  exact: false
  retry: 5
  retry_interval: 1.0
  optional: true          # 超时不报错
```

**命中后**：`last_coord` 会更新为该文本坐标，后续可用 `click target=last`。

---

### 7. `repeat` — 次数循环

**作用**：把 `steps` 里的子步骤重复执行 `times` 次。

**参数**：

| 字段 | 说明 |
|------|------|
| `times` | 循环次数 |
| `steps` | 子步骤列表 |

**示例**：

```yaml
- action: repeat
  remark: "精工 7 轮"
  times: 7
  steps:
    - action: click
      target: coords
      coords: [849, 2282]
      sleep: 0.5
    - action: abort_check
      async: true
      abort_text:
        mode: mixed
        rules:
          - type: must
            keywords: ["最高等级"]
      on_match: break_outer
    - action: click
      target: coords
      coords: [500, 1682]
      sleep: 0.5
```

**控制流**：
- 子步骤抛 `LoopBreak` → 跳出本 `repeat`。
- 子步骤抛 `SkillAbort` → 继续向上传播，由外层 `for_each_coord` 捕获。
- 子步骤失败（返回 `False`）→ 整个 `repeat` 返回 `False`。

**异步 abort 消费时机**：
- 每轮开始前 `check_async_hit(phase="step")`。
- 每轮结束后 `check_async_hit(phase="loop_end")`。

---

### 8. `for_each_coord` — 遍历坐标列表

**作用**：对 `coords_list` 中每个坐标，执行"点击坐标 → 内循环 `steps`"。

**参数**：

| 字段 | 说明 |
|------|------|
| `coords_list` | 坐标列表 `[[x,y], ...]`，也可写成 `[{coord:[x,y], times:N}, ...]` |
| `times` | 每个坐标项**内部循环次数**，默认 1 |
| `steps` | 子步骤列表 |
| `click_wait` | 点击坐标后的等待（秒） |
| `interval` | 每轮内循环之间的间隔（秒） |
| `close_popup_before_next` | 处理完一个坐标后是否发返回键关闭弹窗 |
| `global_abort` | 全局终止词 `{keywords: [...], exact: false}` |
| `abort_text` | 坐标项开始时启动的异步 abort 配置 |

**示例 1：基础遍历**

```yaml
- action: for_each_coord
  remark: "对 4 个技能依次升级，每个 25 次"
  coords_list:
    - [389, 1328]
    - [895, 1313]
    - [375, 1500]
    - [893, 1495]
  click_wait: 0.5
  times: 25
  interval: 0.3
  steps:
    - action: click
      target: last
      times: 1
    - action: click
      coords: [531, 1775]
      times: 2
      interval: 0.2
    - action: click
      coords: [770, 1764]
      times: 2
      interval: 0.2
```

**示例 2：带同步 abort_check 跳过已满级**

```yaml
- action: for_each_coord
  coords_list:
    - [294, 895]
    - [540, 895]
    - [798, 911]
    - [289, 1106]
    - [548, 1117]
    - [832, 1093]
  click_wait: 0.5
  steps:
    # ① 同步检查：满级 → break_outer 跳到下一个坐标
    - action: abort_check
      abort_text:
        mode: mixed
        rules:
          - type: must
            keywords: ["最高等级"]
      on_match: break_outer
      on_miss: next
      retry: 1
      retry_interval: 0.3

    # ② 内层循环：精工 → 确定
    - action: repeat
      times: 7
      steps:
        - action: click
          coords: [849, 2282]
          sleep: 0.5
        - action: abort_check
          async: true
          abort_text:
            mode: mixed
            match_mode: any
            rules:
              - type: must
                keywords: ["最高等级"]
              - type: not
                keywords: ["确定"]
          on_match: break_outer
          consume_at: outer_end
        - action: click
          coords: [500, 1682]
          sleep: 0.5
```

**执行流程**：

```
for idx, coord in enumerate(coords_list):
    stop_async()                       # 清理上一项的异步线程
    last_coord = coord
    touch(coord)                       # 点击坐标
    sleep(click_wait)
    启动 abort_text 的异步监听（若有）
    for loop_idx in range(times):
        check_async_hit("step")        # 检查异步命中
        for sub in steps:
            run_step(sub)              # 子步骤可能抛 SkillAbort / LoopBreak
        check_async_hit("loop_end")
    check_async_hit("outer_end")       # 消费延迟命中
    stop_async()
    if close_popup_before_next:
        发返回键
```

**控制流**：
- 子步骤抛 `SkillAbort` → 捕获，标记本坐标项失败，跳到下一个坐标。
- 子步骤抛 `LoopBreak` → 捕获，结束本坐标项内循环，继续下一个坐标。
- `global_abort` 命中的关键词会触发 `SkillAbort`。

**坐标项两种写法**：

```yaml
# 写法一：纯坐标，times 用顶层 times
coords_list:
  - [389, 1328]
  - [895, 1313]
times: 25

# 写法二：每项单独配 times
coords_list:
  - {coord: [389, 1328], times: 25}
  - {coord: [895, 1313], times: 10}
```

---

### 9. `abort_check` — 条件检查 / 终止

**作用**：检查页面是否出现"终止关键词"，命中后按 `on_match` 控制走向。

**参数**：

| 字段 | 说明 |
|------|------|
| `abort_text` | 终止关键词配置（字符串/列表/规则字典） |
| `on_match` | 命中后走向：`break_outer` / `break_inner` / `next` |
| `on_miss` | 未命中走向（仅同步有效） |
| `async` | `true` 则异步监听，默认 false |
| `consume_at` | 命中消费时机：`step` / `loop_end` / `outer_end`（仅异步） |
| `retry` | 同步重试次数 |
| `retry_interval` | 重试 / 监听间隔 |
| `not_confirm_count` | not 规则连续命中几次才算数，默认 3 |
| `exact` | 是否精确匹配 |
| `region` 等 | 限定检查区域 |

**走向值语义**：

| 值 | 抛出异常 | 被谁捕获 | 效果 |
|----|----------|----------|------|
| `break_outer` | `SkillAbort` | 最外层 `for_each_coord` | 跳到下一个坐标项 |
| `break_inner` | `LoopBreak` | 最近一层 `repeat` / `for_each_coord` | 跳出当前循环 |
| `next` | 无 | — | 继续下一步 |

**消费时机 `consume_at`**：

| 值 | 含义 |
|----|------|
| `step` | 立即消费命中（默认） |
| `loop_end` | 等到最近一层循环结束时消费 |
| `outer_end` | 等到外层 `for_each_coord` 当前项结束时消费 |

**示例 1：同步检查（技能开头，已满级则跳过）**

```yaml
- action: abort_check
  remark: "检查技能是否已满级"
  abort_text:
    mode: mixed
    rules:
      - type: must
        keywords: ["最高等级"]
  on_match: break_outer       # 满级 → 跳到下一个技能
  on_miss: next               # 未满级 → 继续
  retry: 1
  retry_interval: 0.3
  not_confirm_count: 2
```

**示例 2：异步监听（循环中随时打断）**

```yaml
- action: abort_check
  remark: "异步监听满级 或 确定消失"
  async: true
  abort_text:
    mode: mixed
    match_mode: any           # 任一规则命中
    rules:
      - type: must
        keywords: ["最高等级"]
      - type: not
        keywords: ["确定"]
  on_match: break_outer
  consume_at: outer_end       # 等坐标项结束再消费
  retry_interval: 0.3
```

**异步行为**：
- `abort_check async:true` 启动后台线程，按 `retry_interval` 反复 OCR。
- 命中后设置 `_async_hit` 事件，不立即抛异常。
- 在 `check_async_hit(phase)` 调用点根据 `consume_at` 决定是否消费。
- **相同配置会复用线程**，避免 repeat 每轮重启导致计数重置。

---

### 10. `call_flow` — 调用子流程

**作用**：调用 `flows/` 下另一个流程，可带前置/后置动作。

**参数**：

| 字段 | 说明 |
|------|------|
| `flow` | 子流程名（对应 `flows/<name>.yaml` 的文件名） |
| `before` | 子流程执行前的子步骤列表 |
| `after` | 子流程执行后的子步骤列表 |
| `times` | 子流程循环次数，默认取子流程的 `loop_count` |

**示例**：

```yaml
- action: call_flow
  remark: "先强化，再精工"
  flow: 将领技能强化
  before:
    - action: click
      remark: "进入技能强化"
      target: coords
      coords: [278, 355]
      sleep: 0.5
  after:
    - action: wait
      seconds: 1.0
```

**注意**：
- 循环引用检测：`_include_stack` 记录调用链，A→B→A 会报错。
- 子流程内部的 `loop_count` 会被 `call_flow` 的 `times` 覆盖（若指定）。

---

### 11. `run_method` — 调用 Python 方法

**作用**：调用 `ActionRunner` 上的方法，把返回值存到 `_action_data[store]`。

**参数**：

| 字段 | 说明 |
|------|------|
| `method` | 方法名 |
| `store` | 结果存到哪个键（可选） |
| `params` | 传给方法的参数字典 |

**内置方法**：

| 方法 | 作用 |
|------|------|
| `scan_general_skills` | OCR 扫描将领技能等级，写计划文件 |
| `get_click_target` | 读计划文件，点击下一个技能；全部完成抛 `LoopBreak` |
| `update_click_count` | 更新已点次数 |

**示例**：

```yaml
# ① 扫描并生成计划
- action: run_method
  remark: "扫描将领技能等级"
  method: scan_general_skills
  store: data
  params:
    general_coord: [482, 320]
    anchor_coords:
      - [226, 1344]
      - [743, 1344]
      - [228, 1530]
      - [743, 1530]
    pattern: "[Ll][Vv]\\.?\\s*(\\d+)\\s*/\\s*(\\d+)"
    file: "data/general_plan.json"

# ② 读取并点击
- action: run_method
  method: get_click_target
  store: current_target
  params:
    file: "data/general_plan.json"
    anchor_wait: 0.5

# ③ 更新计数
- action: run_method
  method: update_click_count
  params:
    file: "data/general_plan.json"
```

**异常处理**：
- `LoopBreak` / `SkillAbort` 会向上抛，交给上层循环处理。
- 其他异常会被捕获，打印堆栈，返回 `False`。

---

### 12. `dump_ocr` — 打印 OCR（调试）

**作用**：打印当前页面所有 OCR 文本及其坐标。

**示例**：

```yaml
- action: dump_ocr
```

**输出**：

```
📋 当前页面 OCR 内容：
   (540, 1800)  「确定」  conf=0.98
   (300, 1200)  「升级」  conf=0.95
   ...
```

**用途**：确认 OCR 识别效果、标定坐标、排查匹配失败。

---

## 五、`before` / `after` 子步骤

**作用**：任意 action 都可以带 `before` / `after`，在主 action 前后执行子步骤。

**示例**：

```yaml
- action: find_click
  text: "升级"
  before:
    - action: dump_ocr
      remark: "点击前先打印页面"
  after:
    - action: wait
      seconds: 0.5
```

**规则**：
- `before` 失败 → 跳过主 action，返回 `False`。
- `after` 失败 → 返回 `False`。
- 嵌套深度限制 10 层，防循环引用。
- `call_flow` 的 `before` / `after` 由自身 handler 消费，不走通用逻辑。

---

## 六、`expect_text` 规则详解

`expect_text` 用于页面校验，三种写法：

### ① 字符串

```yaml
expect_text: "建造"
```

子串匹配，页面文本包含"建造"即通过。

### ② 列表（OR）

```yaml
expect_text: ["建造", "研究", "升级"]
```

任一命中即通过。

### ③ 规则字典

```yaml
expect_text:
  mode: mixed          # and | or | mixed
  match_mode: all      # all | any（仅 mixed）
  rules:
    - type: must       # must | any | not
      keywords: ["建造"]
    - type: not
      keywords: ["取消"]
```

| mode | 含义 |
|------|------|
| `and` | `keywords` 全部出现 |
| `or` | `keywords` 任一出现 |
| `mixed` | 按 `rules` 逐条判断，`match_mode` 决定合并方式 |

| rule.type | 含义 |
|-----------|------|
| `must` | `keywords` 全部出现 |
| `any` | `keywords` 任一出现 |
| `not` | `keywords` 全部不出现 |

| match_mode | 含义 |
|------------|------|
| `all` | 所有规则都满足（默认） |
| `any` | 任一规则满足 |

---

## 七、控制流与异常

| 异常 | 抛出者 | 捕获者 | 效果 |
|------|--------|--------|------|
| `SkillAbort` | `abort_check on_match=break_outer` / 全局终止 | `for_each_coord` | 跳到下一个坐标项 |
| `LoopBreak` | `abort_check on_match=break_inner` / `get_click_target` | `repeat` / `for_each_coord` | 跳出当前循环 |
| `UserExit` | 用户操作 | `main.py` | 退出程序 |

**传播规则**：
- `SkillAbort` 会**穿透** `repeat`，直到被 `for_each_coord` 捕获。
- `LoopBreak` 被**最近一层** `repeat` / `for_each_coord` 捕获。
- 子步骤返回 `False` 不会抛异常，只是让父步骤返回 `False`。

---

## 八、完整配置示例（综合）

```yaml
# ============================================
# 流程：综合示例
# ============================================
loop_count: 2

steps:
  # ① 调试：先看页面有什么
  - action: dump_ocr
    remark: "打印初始页面"

  # ② 查找并点击（带页面校验）
  - action: find_click
    remark: "点击升级按钮"
    text: "升级"
    exact: false
    expect_text:
      mode: or
      keywords: ["建造", "研究"]
    region: [400, 2000, 700, 2400]
    retry: 3
    retry_interval: 0.5
    times: 2
    interval: 0.5
    sleep: 0.5

  # ③ 遍历 6 个技能
  - action: for_each_coord
    remark: "对 6 个技能依次精工"
    coords_list:
      - [294, 895]
      - [540, 895]
      - [798, 911]
      - [289, 1106]
      - [548, 1117]
      - [832, 1093]
    click_wait: 0.5
    global_abort:
      keywords: ["网络错误"]
      exact: false

    steps:
      # ③-1 同步检查满级
      - action: abort_check
        abort_text:
          mode: mixed
          rules:
            - type: must
              keywords: ["最高等级"]
        on_match: break_outer
        on_miss: next
        retry: 1
        retry_interval: 0.3

      # ③-2 内层循环 7 轮
      - action: repeat
        times: 7
        steps:
          - action: click
            coords: [849, 2282]
            sleep: 0.5
          - action: abort_check
            async: true
            abort_text:
              mode: mixed
              match_mode: any
              rules:
                - type: must
                  keywords: ["最高等级"]
                - type: not
                  keywords: ["确定"]
            on_match: break_outer
            consume_at: outer_end
            retry_interval: 0.3
          - action: click
            coords: [500, 1682]
            sleep: 0.5

  # ④ 调用子流程
  - action: call_flow
    flow: 将领技能强化
    before:
      - action: click
        coords: [278, 355]
        sleep: 0.5
    after:
      - action: wait
        seconds: 1.0

  # ⑤ 调用 Python 方法
  - action: run_method
    method: scan_general_skills
    store: data
    params:
      anchor_coords: [[226, 1344], [743, 1344]]
      pattern: "[Ll][Vv]\\.?\\s*(\\d+)\\s*/\\s*(\\d+)"
      file: "data/general_plan.json"

  # ⑥ 数据驱动点击
  - action: repeat
    times: 100
    steps:
      - action: run_method
        method: get_click_target
        params:
          file: "data/general_plan.json"
      - action: click
        coords: [538, 1761]
        times: 2
      - action: click
        coords: [762, 1761]
        times: 2
      - action: run_method
        method: update_click_count
        params:
          file: "data/general_plan.json"
```

---

## 九、快速参考：action 与关键字段对照

| action | 必填字段 | 关键可选字段 | 典型用途 |
|--------|----------|--------------|----------|
| `click` | `coords`（target=coords） | `target`, `times`, `interval`, `sleep` | 固定坐标点击 |
| `find` | `text` | `exact`, `expect_text`, `region`, `retry`, `optional` | 查找并记录坐标 |
| `find_click` | `text` | `expect_text`, `region`, `retry`, `optional`, `target` | 查找并点击 |
| `poll_click` | `coords` 或 `coords_list` | `expect_text`, `click_text`, `times`, `interval` | 轮询点直到页面变化 |
| `wait` | `seconds` | — | 纯等待 |
| `wait_text` | `text` | `retry`, `retry_interval`, `optional` | 等文本出现 |
| `repeat` | `times`, `steps` | — | 次数循环 |
| `for_each_coord` | `coords_list`, `steps` | `times`, `click_wait`, `interval`, `global_abort`, `abort_text` | 遍历坐标 |
| `abort_check` | `abort_text` | `on_match`, `on_miss`, `async`, `consume_at`, `not_confirm_count` | 条件终止 |
| `call_flow` | `flow` | `before`, `after`, `times` | 调用子流程 |
| `run_method` | `method` | `store`, `params` | 调用 Python 方法 |
| `dump_ocr` | — | — | 调试打印 OCR |

---

## 十、核心要点总结

1. **`action` 是核心**：决定这个 step 干什么，其他字段都是它的参数。
2. **通用字段 vs 专属字段**：`remark` / `enabled` / `sleep` / `before` / `after` 所有 action 通用；`coords` / `text` / `abort_text` 等按 action 区分。
3. **默认值层级**：step 内 > `config.yaml defaults` > 代码硬编码。
4. **控制流三兄弟**：`break_outer`（跳坐标项）、`break_inner`（跳循环）、`next`（继续）。
5. **异步 abort 两要素**：`consume_at` 决定何时消费，`on_match` 决定消费后怎么走。
6. **`for_each_coord` 是主力**：遍历 + 内循环 + 同步/异步 abort，几乎能覆盖所有"多目标依次处理"场景。
7. **`call_flow` 做复用**：小流程组合成大流程，注意循环引用检测。
8. **`run_method` 做扩展**：YAML 表达不了的复杂逻辑，用 Python 方法补。
9. **`dump_ocr` 是救星**：调不通时先打印页面，看 OCR 到底识别到什么。
10. **`before` / `after` 很灵活**：任何 action 都能挂前置/后置，适合做"进入页面 → 操作 → 等待"的模式。
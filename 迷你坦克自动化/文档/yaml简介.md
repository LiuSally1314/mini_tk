# YAML 配置简介

## 一、整体结构

```
config/
├── config.yaml              # 主配置（全局设置 + 默认值 + 激活流程）
└── flows/                   # 各业务流程配置
    ├── 将领升级.yaml
    ├── 将领第二次升级.yaml
    ├── 将领技能精工.yaml
    ├── 将领技能强化.yaml
    ├── 将领技能精工强化.yaml
    ├── 将领技能升级.yaml
    ├── 将领技能升级2.yaml
    ├── 建筑升级.yaml
    └── 邮箱领取.yaml
```

**关系**：
- `config.yaml` 只放**全局设置**和**默认值**。
- `flows/*.yaml` 每个文件是**一个完整流程**，文件名即流程名。
- 程序启动时自动扫描 `flows/` 下所有 YAML，按文件名注册流程。
- `config.yaml` 里的 `active_flow` 决定启动时执行哪个流程。
- 流程之间可以通过 `call_flow` 互相调用。

---

## 二、主配置 config.yaml

```yaml
device:
  uri: "Android:///192.168.31.102:37781"   # 设备连接地址

output:
  json_filename: "ocr_result.json"          # OCR 结果文件名
  query_json_filename: "query_result.json"  # 查询结果文件名
  base_dir: "截屏"                          # 截图目录

defaults:                                   # 所有步骤的默认参数（步骤内可覆盖）
  retry: 3                                  # OCR 查找失败重试次数
  retry_interval: 1.0                       # 重试间隔（秒）
  interval: 0.5                             # 通用动作间隔（秒）
  exact: true                               # 是否精确匹配
  sleep: 0.1                                # 每步后休眠（秒）
  enabled: true                             # 步骤是否启用

active_flow: "将领技能升级"                  # 当前激活的流程名
flows_dir: "config/flows"                   # 流程目录
```

**关键点**：
- `defaults` 是**兜底值**，流程步骤里没写的字段会从这里取。
- 步骤里写了同名字段，则以步骤内的为准。
- `active_flow` 就是 `flows/` 下某个 YAML 的**文件名（不带扩展名）**。

---

## 三、流程 YAML 的通用结构

每个 `flows/*.yaml` 都是这个骨架：

```yaml
loop_count: 1          # 整个流程循环几次

steps:                 # 步骤列表，从上到下依次执行
  - action: click      # 第 1 步：点击
    ...
  - action: find_click # 第 2 步：查找并点击
    ...
  - action: repeat     # 第 3 步：循环
    ...
```

| 顶层字段 | 说明 |
|----------|------|
| `loop_count` | 整个流程重复执行次数，默认 1 |
| `steps` | 步骤列表，每个元素是一个动作 |

---

## 四、步骤（step）的通用字段

每个步骤都是 `action` + 若干参数：

```yaml
- action: click           # 必填，动作名
  remark: "日志说明"       # 可选，打印在日志里
  text: "说明文本"         # 可选，多数动作用它作查找目标
  target: coords          # 可选，点击目标来源
  coords: [553, 2257]     # 可选，坐标
  coords_list: [[...]]    # 可选，坐标列表
  times: 1                # 可选，次数
  interval: 0.5           # 可选，间隔（秒）
  retry: 3                # 可选，OCR 重试次数
  retry_interval: 1.0     # 可选，重试间隔（秒）
  exact: true             # 可选，是否精确匹配
  sleep: 0.5              # 可选，步骤后休眠（秒）
  optional: false         # 可选，找不到时是否跳过
  enabled: true           # 可选，是否启用本步
  before: [...]           # 可选，前置子步骤
  after: [...]            # 可选，后置子步骤
  expect_text: "..."      # 可选，期望出现的页面关键词
```

**未写的字段**会自动从 `config.yaml` 的 `defaults` 取默认值。

---

## 五、flows/ 下各流程逐一简介

### 1. 邮箱领取.yaml

**作用**：循环领取邮箱里的 GM 邮件并删除。

```yaml
loop_count: 100

steps:
  - action: click
    remark: "点击第一个邮件"
    target: coords
    coords: [542, 517]
    sleep: 0.5

  - action: click
    remark: "领取"
    target: coords
    coords: [555, 2171]
    sleep: 0.5

  - action: click
    remark: "删除邮箱"
    target: coords
    coords: [843, 2317]
    sleep: 0.5
```

**特点**：
- 全部是**固定坐标点击**，`text` 只作为日志说明。
- 循环 100 次，适合批量处理邮件。
- 没有 OCR 查找，速度快但依赖分辨率。

---

### 2. 建筑升级.yaml

**作用**：循环查找"升级"按钮并点击，带页面校验。

```yaml
loop_count: 100

steps:
  - action: find_click
    text: "升级"
    expect_text: "建造"          # 简单字符串
    times: 2
    interval: 0.5
    sleep: 0.5

  - action: find_click
    text: "加速"
    expect_text:                # OR 模式
      mode: or
      keywords: ["建造", "研究", "升级"]
    times: 1
    sleep: 0.5

  - action: find_click
    text: "确定"
    expect_text:                # AND 模式
      mode: and
      keywords: ["建造"]
    times: 1
    sleep: 0.5
```

**特点**：
- 演示了 `expect_text` 的**三种写法**：字符串、OR 列表、AND 规则。
- `find_click` 会先 OCR 查找 `text`，找到后点击。
- `expect_text` 用于校验页面状态，不满足会重试。

---

### 3. 将领升级.yaml

**作用**：将领 1→40→50→60 级 + 两次突破 + 一次授勋。

```yaml
loop_count: 1

steps:
  - action: click
    remark: "进入升级 1->40"
    text: "升级"
    target: coords
    coords: [553, 2257]
    sleep: 0.5

  - action: click
    remark: "升级 1->40"
    text: "升39级"
    target: coords
    coords: [858, 2257]
    sleep: 0.5

  # ... 后续都是类似结构
```

**特点**：
- 全部是**固定坐标点击**，共 17 步。
- `text` 只是日志说明，让日志可读。
- 流程线性、无分支、无循环。
- 依赖固定 UI 布局，适合分辨率稳定的模拟器。

---

### 4. 将领第二次升级.yaml

**作用**：领悟技能 + 50→70 级 + 第二次授勋。

```yaml
loop_count: 1

steps:
  - action: click
    remark: "进入第一个领悟"
    coords: [362, 1888]
    sleep: 0.5

  - action: click
    remark: "领悟 ×60"
    coords: [772, 2282]
    times: 60           # 一次点击 60 次
    interval: 0.2

  - action: click
    remark: "领悟第一个技能"
    coords: [254, 1791]
    sleep: 0.5

  # ... 后续升级、授勋
```

**特点**：
- 用 `times: 60` + `interval: 0.2` 实现**连点**。
- 同样是固定坐标。
- 是"将领升级"的续篇，通常在前一个流程之后执行。

---

### 5. 将领技能强化.yaml

**作用**：对 6 个技能依次执行"一键强化 → 进阶 → 确定"，共 10 轮。

```yaml
loop_count: 1

steps:
  - action: for_each_coord
    remark: "对技能 1~6 依次执行：强化 → 进阶 → 确定 ×10 轮"
    click_wait: 0.5
    coords_list:
      - [294, 895]
      - [540, 895]
      - [798, 911]
      - [289, 1106]
      - [548, 1117]
      - [832, 1093]

    steps:
      - action: abort_check
        remark: "检查技能是否已满级"
        abort_text:
          mode: mixed
          rules:
            - type: must
              keywords: ["最高等级"]
        on_match: break_outer
        on_miss: next
        retry: 1

      - action: repeat
        times: 10
        steps:
          - action: abort_check
            async: true
            abort_text:
              mode: mixed
              rules:
                - type: must
                  keywords: ["最高等级"]
            on_match: break_outer
            retry_interval: 0.3

          - action: click
            remark: "一键强化"
            coords: [356, 2288]
            sleep: 0.5

          - action: find_click
            remark: "等进阶出现并点击（可选）"
            text: "进阶"
            exact: false
            coords: [540, 2277]
            region_size: 300
            retry: 4
            retry_interval: 0.2
            optional: true

          - action: click
            remark: "确定进阶成功"
            coords: [542, 1700]
            sleep: 0.1
```

**特点**：
- 用 `for_each_coord` **遍历 6 个技能坐标**。
- 每个技能项内部先做一次**同步 abort_check**，已满级就跳过。
- 内层 `repeat ×10` 中嵌入**异步 abort_check**，随时监听"最高等级"。
- `find_click` 带 `optional: true`，进阶按钮没出现就跳过。
- 综合运用了 `for_each_coord` + `repeat` + 同步/异步 `abort_check`。

---

### 6. 将领技能精工.yaml

**作用**：对 6 个技能依次执行"精工 → 确定 ×7 轮"。

```yaml
loop_count: 1

steps:
  - action: for_each_coord
    remark: "对技能 1~6 依次执行：精工 → 确定 ×7 轮"
    click_wait: 0.5
    coords_list:
      - [294, 895]
      - [540, 895]
      - [798, 911]
      - [289, 1106]
      - [548, 1117]
      - [832, 1093]

    steps:
      - action: abort_check
        remark: "检查技能是否已满级"
        abort_text:
          mode: mixed
          rules:
            - type: must
              keywords: ["最高等级"]
        on_match: break_outer
        on_miss: next
        retry: 1
        retry_interval: 0.3
        not_confirm_count: 2

      - action: repeat
        times: 7
        steps:
          - action: click
            remark: "精工"
            coords: [849, 2282]
            sleep: 0.5

          - action: abort_check
            remark: "出现最高等级 或 没出现确定 → 打断本 repeat"
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
            remark: "确定"
            coords: [500, 1682]
            sleep: 0.5
```

**特点**：
- 结构与"技能强化"类似，但循环次数是 7。
- 异步 abort_check 用 `match_mode: any`，**"最高等级"出现 或 "确定"消失**都触发。
- `consume_at: outer_end` 表示命中后**等到当前坐标项结束再消费**。
- `not_confirm_count: 2` 表示 not 规则要连续命中 2 次才算数。

---

### 7. 将领技能精工强化.yaml（组合流程）

**作用**：先调"将领技能强化"，再调"将领技能精工"。

```yaml
loop_count: 1

steps:
  - action: call_flow
    flow: 将领技能强化
    before:
      - action: click
        remark: "进入技能强化"
        coords: [278, 355]
        sleep: 0.5
    after:
      - action: wait
        seconds: 1.0

  - action: call_flow
    flow: 将领技能精工
    before:
      - action: click
        remark: "进入技能精工"
        coords: [779, 355]
        sleep: 0.5
    after:
      - action: wait
        seconds: 1.0
```

**特点**：
- 本身**没有业务逻辑**，只是调度器。
- 用 `call_flow` 调用其他流程文件。
- `before` / `after` 是子流程执行前后的附加动作。
- 演示了**流程复用**：把两个独立流程串起来。
- `_include_stack` 会检测循环引用，避免 A 调 B、B 调 A。

---

### 8. 将领技能升级2.yaml

**作用**：对 4 个技能依次升级，每个技能循环 25 次。

```yaml
loop_count: 1

steps:
  - action: for_each_coord
    remark: "对4个技能依次升级，每个技能循环25次"
    coords_list:
      - [389, 1328]
      - [895, 1313]
      - [375, 1500]
      - [893, 1495]
    click_wait: 0.5
    times: 25                # 每个坐标项内部循环 25 次
    interval: 0.3
    close_popup_before_next: false

    steps:
      - action: click
        remark: "点技能框"
        target: last
        times: 1
        sleep: 0.3

      - action: click
        remark: "升级（左）"
        coords: [531, 1775]
        times: 2
        interval: 0.2

      - action: click
        remark: "升级（右）"
        coords: [770, 1764]
        times: 2
        interval: 0.2
```

**特点**：
- `for_each_coord` 带 `times: 25`，表示**每个坐标项内部再循环 25 次**。
- `target: last` 复用上一次 `for_each_coord` 记录的坐标（即当前技能框）。
- 是"将领技能升级"的**简化版**，不依赖外部数据文件。
- 适合技能数量固定、升级次数固定的场景。

---

### 9. 将领技能升级.yaml（数据驱动版）

**作用**：OCR 扫描技能等级 → 生成计划 → 按计划点击升级。

```yaml
loop_count: 1

steps:
  # ① 初始化数据
  - action: run_method
    remark: "扫描将领技能等级，写入数据文件"
    method: scan_general_skills
    store: data
    params:
      general_coord: [482, 320]
      general_region_w: 300
      general_region_h: 120
      anchor_coords:
        - [226, 1344]
        - [743, 1344]
        - [228, 1530]
        - [743, 1530]
      pattern: "[Ll][Vv]\\.?\\s*(\\d+)\\s*/\\s*(\\d+)"
      region_w: 300
      region_h: 300
      default_times: 0
      value_per_unit: 1
      debug: true
      file: "data/general_plan.json"

  # ② 固定循环 100 轮
  - action: repeat
    times: 100
    steps:
      # ③ 读数据，判断+点击
      - action: run_method
        method: get_click_target
        store: current_target
        params:
          file: "data/general_plan.json"
          anchor_wait: 0.5

      # ④⑤ 点击升级（左/右）
      - action: click
        coords: [538, 1761]
        times: 2
        interval: 0.2

      - action: click
        coords: [762, 1761]
        times: 2
        interval: 0.2

      # ⑥ 更新已点次数
      - action: run_method
        method: update_click_count
        params:
          file: "data/general_plan.json"
```

**特点**：
- 最"智能"的流程，**由 OCR 数据驱动**。
- `scan_general_skills`：整页 OCR，用正则抓 `LV.x/y`，匹配到 4 个锚点，算出每个技能还需点几次，写入 `data/general_plan.json`。
- `get_click_target`：读文件，找下一个 `done < need` 的技能，点击它；全部完成时抛 `LoopBreak` 跳出 repeat。
- `update_click_count`：每次点击后 `done += 1`。
- 适合**技能等级动态变化**、需要精确控制点击次数的场景。

---

## 六、flows/ 流程对比表

| 流程 | 循环 | 核心动作 | 是否 OCR | 特点 |
|------|------|----------|----------|------|
| 邮箱领取 | 100 | click | 否 | 纯固定坐标，批量领邮件 |
| 建筑升级 | 100 | find_click | 是 | 演示 expect_text 三种写法 |
| 将领升级 | 1 | click | 否 | 线性 17 步，固定坐标 |
| 将领第二次升级 | 1 | click | 否 | 连点 60 次，固定坐标 |
| 将领技能强化 | 1 | for_each_coord + repeat + abort_check | 是 | 异步监听满级 |
| 将领技能精工 | 1 | for_each_coord + repeat + abort_check | 是 | 异步 + not 规则 + 延迟消费 |
| 将领技能精工强化 | 1 | call_flow | 否 | 组合流程，调度器 |
| 将领技能升级2 | 1 | for_each_coord + click | 否 | 简化版，固定 25 次 |
| 将领技能升级 | 1 | run_method + repeat | 是 | 数据驱动，OCR 扫描 + 计划文件 |

---

## 七、flows/ 配置的通用设计模式

### 模式 1：纯固定坐标（最简单）

```yaml
- action: click
  text: "日志说明"
  target: coords
  coords: [x, y]
  times: 1
  sleep: 0.5
```

适用：UI 稳定、分辨率固定、步骤线性。

### 模式 2：OCR 查找 + 点击

```yaml
- action: find_click
  text: "升级"
  expect_text: "建造"
  times: 2
```

适用：按钮位置会变，或需要页面校验。

### 模式 3：遍历坐标 + 内循环

```yaml
- action: for_each_coord
  coords_list: [[x1,y1], [x2,y2], ...]
  times: 10
  steps:
    - action: click
      target: last
    - action: click
      coords: [x, y]
```

适用：多个同类目标（技能、建筑）依次处理。

### 模式 4：循环 + 异步终止

```yaml
- action: repeat
  times: 7
  steps:
    - action: click
      coords: [x, y]
    - action: abort_check
      async: true
      abort_text:
        mode: mixed
        rules:
          - type: must
            keywords: ["最高等级"]
      on_match: break_outer
```

适用：循环次数不确定，需要提前退出（如满级、弹窗消失）。

### 模式 5：数据驱动

```yaml
- action: run_method
  method: scan_general_skills
  params: {...}

- action: repeat
  times: 100
  steps:
    - action: run_method
      method: get_click_target
    - action: click
      coords: [x, y]
    - action: run_method
      method: update_click_count
```

适用：需要先扫描页面状态，再按状态精确操作。

### 模式 6：组合流程

```yaml
- action: call_flow
  flow: 子流程名
  before: [...]
  after: [...]
```

适用：把多个流程串起来，或复用已有流程。

---

## 八、flows/ 配置的关键要点

1. **文件名即流程名**：`将领技能升级.yaml` → 流程名 `将领技能升级`，`call_flow` 和 `active_flow` 都用这个名字。
2. **顶层只有 `loop_count` 和 `steps`**：其他字段（如 `defaults`）不在这里配。
3. **步骤内可覆盖默认值**：如 `sleep: 0.5` 会覆盖 `config.yaml` 里的 `defaults.sleep`。
4. **`text` 不一定是查找目标**：在 `click` 动作里它只是日志；在 `find` / `find_click` 里才是 OCR 目标。
5. **`coords` 是绝对坐标**：基于特定分辨率，换设备要重新标定。
6. **`for_each_coord` 的 `times` 是每项内部循环**：不是遍历次数，遍历次数由 `coords_list` 长度决定。
7. **`abort_check` 的 `on_match` 决定控制流**：`break_outer` 跳到下一个坐标项，`break_inner` 跳出当前循环，`next` 继续。
8. **`call_flow` 可以带 `before` / `after`**：实现"进入某页面 → 执行子流程 → 等待"的模式。
9. **`run_method` 是扩展点**：流程里能调用 Python 方法，实现复杂逻辑。
10. **`loop_count` 是流程级循环**：整个 `steps` 列表会重复执行 `loop_count` 次。

---

## 九、一个流程 YAML 的完整注释示例

```yaml
# ============================================
# 流程：示例流程
# 说明：演示各种字段的用法
# ============================================

loop_count: 3          # 整个流程重复 3 次

steps:
  # ---------- 1. 固定坐标点击 ----------
  - action: click
    remark: "点击确认按钮"           # 日志说明
    text: "确认"                     # 仅日志用
    target: coords                   # 用本步 coords
    coords: [540, 1800]              # 绝对坐标
    times: 1                         # 点 1 次
    sleep: 0.5                       # 本步后休眠 0.5s
    enabled: true                    # 启用

  # ---------- 2. OCR 查找并点击 ----------
  - action: find_click
    remark: "查找升级按钮"
    text: "升级"                     # OCR 目标
    exact: false                     # 模糊匹配
    expect_text: "建造"              # 页面校验
    region: [400, 2000, 700, 2400]   # 限定查找区域
    retry: 3                         # 重试 3 次
    retry_interval: 0.5              # 重试间隔
    optional: false                  # 找不到就报错

  # ---------- 3. 遍历坐标 + 内循环 ----------
  - action: for_each_coord
    remark: "处理 4 个技能"
    coords_list:
      - [389, 1328]
      - [895, 1313]
      - [375, 1500]
      - [893, 1495]
    click_wait: 0.5                  # 点击坐标后等待
    times: 10                        # 每项内部循环 10 次
    interval: 0.3                    # 每轮循环间隔
    global_abort:                    # 全局终止词
      keywords: ["网络错误"]
      exact: false
    steps:
      - action: click
        target: last                 # 用上一次记录的坐标
        times: 1
      - action: click
        coords: [531, 1775]
        times: 2
        interval: 0.2

  # ---------- 4. 循环 + 异步终止 ----------
  - action: repeat
    remark: "精工 7 轮"
    times: 7
    steps:
      - action: click
        coords: [849, 2282]
        sleep: 0.5
      - action: abort_check
        async: true                  # 异步监听
        abort_text:
          mode: mixed
          match_mode: any            # 任一规则命中
          rules:
            - type: must
              keywords: ["最高等级"]
            - type: not
              keywords: ["确定"]
        on_match: break_outer        # 跳到外层下一个坐标
        consume_at: outer_end        # 等到坐标项结束再消费
        retry_interval: 0.3
      - action: click
        coords: [500, 1682]
        sleep: 0.5

  # ---------- 5. 调用子流程 ----------
  - action: call_flow
    flow: 将领技能强化
    before:
      - action: click
        coords: [278, 355]
    after:
      - action: wait
        seconds: 1.0

  # ---------- 6. 调用 Python 方法 ----------
  - action: run_method
    method: scan_general_skills
    store: data
    params:
      anchor_coords: [[226, 1344], [743, 1344]]
      pattern: "[Ll][Vv]\\.?\\s*(\\d+)\\s*/\\s*(\\d+)"
      file: "data/general_plan.json"
```

---

## 十、总结

**config.yaml**：
- 全局设置 + 默认值 + 激活流程。
- 不改流程逻辑，只改这里就能切换设备、调整默认参数、切换流程。

**flows/*.yaml**：
- 每个文件是一个完整流程，文件名即流程名。
- 顶层只有 `loop_count` 和 `steps`。
- 步骤由 `action` 驱动，字段可覆盖全局默认值。
- 9 个流程覆盖了从"纯固定坐标"到"OCR 数据驱动"的完整谱系。
- 通过 `call_flow` 可以组合复用，通过 `run_method` 可以扩展 Python 逻辑。

**核心设计思想**：
- **配置与代码分离**：业务变化只改 YAML。
- **动作原子化**：click / find / repeat / for_each_coord / abort_check 等可自由组合。
- **OCR 兜底**：需要时用文本定位，不需要时用固定坐标。
- **异步终止**：让不确定次数的循环能提前退出。
- **流程复用**：小流程组合成大流程。
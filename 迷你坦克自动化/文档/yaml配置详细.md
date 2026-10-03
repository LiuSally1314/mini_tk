# Action 动作详细文档

本文档详细说明 `core/actions.py` 中 `ActionRunner` 支持的所有动作（`action` 字段），以及每个动作的配置字段、行为、返回值和典型用法。

---

## 通用字段

所有 step 都支持以下字段，先于具体动作处理：

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `action` | str | 必填 | 动作名，决定分发到哪个 handler |
| `enabled` | bool | `defaults.enabled`（true） | 为 false 时跳过该步骤，直接返回 True |
| `remark` | str | - | 日志备注，打印 `📝 {remark}` |
| `text` | str | - | 日志文本，remark 未配置时打印 `📝 [text] {text}` |
| `name` | str | - | 日志名称，同上；也用于坐标缓存 key |
| `before` | list | - | 前置子步骤列表，主步骤前执行（`call_flow` 除外） |
| `after` | list | - | 后置子步骤列表，主步骤后执行（`call_flow` 除外） |

**通用默认值**（来自 `config.yaml` 的 `defaults`）：

| 键 | 默认 | 说明 |
|---|---|---|
| `retry` | 3 | OCR 查找失败重试次数 |
| `retry_interval` | 1.0 | 重试间隔（秒） |
| `interval` | 0.5 | 通用动作间隔（点击/循环，秒） |
| `exact` | true | 文本是否精确匹配 |
| `sleep` | 0.1 | 每步执行后休眠（秒） |
| `enabled` | true | 步骤是否启用 |
| `cache_ttl` | 300 | 坐标缓存过期时间（秒） |

**步骤内可覆盖任意默认值**。

**before / after 递归深度限制**：`run_step` 的 `_depth` 超过 10 会报错并返回 False，防止循环引用。

---

## 1. `find` — 查找文本

在页面中查找文本，找到后把坐标存到 `self.last_coord`，供后续 `click`（`target: last`）使用。

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `text` | str 或 list | - | 要查找的目标文本，列表时任一命中即可 |
| `expect_text` | str 或 list 或 dict | - | 页面确认规则，见下方说明 |
| `confirm_keyword` | str 或 list 或 dict | - | `expect_text` 的别名 |
| `page_keyword` | str 或 list 或 dict | - | `expect_text` 的别名 |
| `exact` | bool | `defaults.exact` | 是否精确匹配 |
| `retry` | int | `defaults.retry` | 重试次数 |
| `retry_interval` | float | `defaults.retry_interval` | 重试间隔 |
| `region` | [x1,y1,x2,y2] | - | 限定查找区域 |
| `coords` | [x,y] | - | 配合 `region_size` / `region_w` / `region_h` 生成区域（`region` 未配置时生效） |
| `region_size` | float | - | 以 `coords` 为中心的方形区域边长 |
| `region_w` | float | `region_size` 或 200 | 以 `coords` 为中心的矩形区域宽 |
| `region_h` | float | `region_size` 或 200 | 以 `coords` 为中心的矩形区域高 |
| `index` | int | 0 | 目标文本命中多个时选第几个（支持负数） |
| `optional` | bool | false | 未找到时是否视为成功继续 |

### 行为

1. 若配置了 `expect_text` 且是**字符串**：把 `text` 作为 `query`、`expect_text` 作为 `page`，一起交给 `_find_with_retry_multi`，两者都命中才算成功。
2. 若 `expect_text` 是**字典或列表**：先调 `_check_page` 做页面确认（带重试），再查找 `text`。
3. 若只配了 `text`：直接查找。
4. 若都没配：直接返回 True。
5. 找到后 `self.last_coord = coord`。
6. 未找到：`optional=true` 时打印警告并返回 True，否则打印警告加上下文返回 False。

### 示例

```yaml
# 简单查找
- action: find
  text: "升级"
  exact: false

# 带页面确认
- action: find
  text: "确定"
  expect_text:
    mode: mixed
    rules:
      - type: must
        keywords: ["确认升级"]

# 限定区域 + 选第二个
- action: find
  text: "领取"
  region: [0, 1000, 1080, 1920]
  index: 1

# 用坐标加尺寸生成区域
- action: find
  text: "进阶"
  coords: [540, 2277]
  region_size: 300

# 可选查找
- action: find
  text: "确定"
  optional: true
  retry: 1
```

---

## 2. `click` — 点击

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `target` | str | `"last"` | `last` 或 `skill` 用 `last_coord`；其他值从 `coords` 取 |
| `coords` | [x,y] | - | `target` 非 last/skill 时的坐标 |
| `offset_x` | float | 0 | x 偏移，叠加到最终坐标 |
| `offset_y` | float | 0 | y 偏移，叠加到最终坐标 |
| `times` | int | 1 | 点击次数 |
| `interval` | float | `defaults.interval` | 多次点击之间的间隔 |
| `sleep` | float | `defaults.sleep` | 点击完成后的休眠 |
| `expect_text` | str 或 list 或 dict | - | 点击前做页面确认 |
| `confirm_keyword` | str 或 list 或 dict | - | `expect_text` 的别名 |
| `page_keyword` | str 或 list 或 dict | - | `expect_text` 的别名 |
| `optional` | bool | false | `target=last` 但无可用坐标时是否跳过 |

### 行为

1. 若配置了页面确认规则，先 `_check_page`，失败返回 False。
2. `target=last` 或 `target=skill` 时用 `self.last_coord`；为空且 `optional=true` 则跳过点击返回 True；否则报错返回 False。
3. `target` 为其他值时，从 `step["coords"]` 取坐标。
4. 应用 `offset_x` 和 `offset_y` 偏移。
5. 循环 `times` 次点击，每次前检查异步终止。
6. 完成后按 `sleep` 休眠。

### 示例

```yaml
# 点击上一次 find 的坐标
- action: click
  target: last
  times: 1

# 固定坐标点击
- action: click
  target: coords
  coords: [832, 2091]
  times: 2
  interval: 0.1

# 带偏移
- action: click
  target: last
  offset_y: -180
  times: 1

# 无坐标可点但允许跳过
- action: click
  target: last
  optional: true
```

---

## 3. `find_click` — 查找并点击

`find` 加 `click` 的组合，支持坐标缓存。

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `text` | str 或 list | - | 要查找的目标文本 |
| `expect_text` | str 或 list 或 dict | - | 页面确认规则 |
| `confirm_keyword` | str 或 list 或 dict | - | `expect_text` 的别名 |
| `page_keyword` | str 或 list 或 dict | - | `expect_text` 的别名 |
| `exact` | bool | `defaults.exact` | 是否精确匹配 |
| `retry` | int | `defaults.retry` | 重试次数 |
| `retry_interval` | float | `defaults.retry_interval` | 重试间隔 |
| `region` | [x1,y1,x2,y2] | - | 限定查找区域 |
| `coords` | [x,y] | - | 配合 `region_size` 等生成区域；若 `target=coords` 则作为点击坐标 |
| `region_size` | float | - | 以 `coords` 为中心的方形区域边长 |
| `region_w` | float | `region_size` 或 200 | 区域宽 |
| `region_h` | float | `region_size` 或 200 | 区域高 |
| `index` | int | 0 | 命中多个时选第几个 |
| `optional` | bool | false | 未找到时是否视为成功继续 |
| `name` | str | - | 坐标缓存 key，配置后启用缓存 |
| `cache_ttl` | float | `defaults.cache_ttl`（300） | 缓存过期秒数 |
| `target` | str | - | 若为 `coords`，走 `do_click` 直接用 `coords` 点击 |
| `offset_x` | float | 0 | x 偏移 |
| `offset_y` | float | 0 | y 偏移 |
| `times` | int | 1 | 点击次数 |
| `interval` | float | `defaults.interval` | 点击间隔 |
| `sleep` | float | `defaults.sleep` | 完成后休眠 |

### 行为

1. 若配了 `name`：先查 `data/coord_cache.json`，命中且未过期则直接 `last_coord = cached` 并点击。
2. 缓存未命中：执行 `do_find`。
3. 找到后把坐标写入缓存（`_store_cached_coord`）。
4. 若 `target=coords`：调用 `do_click` 用 `coords` 点击。
5. 否则 `target=last` 点击刚找到的坐标。

### 示例

```yaml
# 带缓存的查找点击
- action: find_click
  name: "点击第一个邮件"
  text: "GM邮件"
  index: 0
  cache_ttl: 6000
  times: 1
  sleep: 3

# 查找后点击 coords（不用 last）
- action: find_click
  text: "进阶"
  exact: false
  coords: [540, 2277]
  region_size: 300
  retry: 4
  retry_interval: 0.2
  optional: true

# 查找后带偏移点击
- action: find_click
  name: "领取"
  text: "领取"
  offset_y: -180
  cache_ttl: 6000
  times: 1
  sleep: 2
```

---

## 4. `wait` — 等待

### 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `seconds` | float | 是 | 等待秒数 |

### 行为

分片（0.2s）sleep，每片前检查异步终止，期间可被 `break_outer` 或 `break_inner` 打断。

### 示例

```yaml
- action: wait
  seconds: 1.0
```

---

## 5. `wait_text` — 等待文本出现

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `text` | str | 必填 | 等待的目标文本 |
| `exact` | bool | `defaults.exact` | 是否精确匹配 |
| `retry` | int | `defaults.retry` | 重试次数 |
| `retry_interval` | float | `defaults.retry_interval` | 重试间隔 |
| `index` | int | 0 | 命中多个时选第几个 |
| `region` | [x1,y1,x2,y2] | - | 限定区域 |
| `coords` | [x,y] | - | 配合 `region_size` 等生成区域 |
| `region_size` | float | - | 以 `coords` 为中心的方形区域边长 |
| `region_w` | float | `region_size` 或 200 | 区域宽 |
| `region_h` | float | `region_size` 或 200 | 区域高 |
| `optional` | bool | false | 超时是否视为成功 |

### 行为

循环 `retry` 次，每次调 `finder.find_text`；命中则 `last_coord = coord` 返回 True；否则 sleep `retry_interval` 后重试。全部失败：`optional=true` 返回 True，否则打印警告加上下文返回 False。

### 示例

```yaml
- action: wait_text
  text: "升级成功"
  retry: 5
  retry_interval: 0.5
  optional: true
```

---

## 6. `abort_check` — 终止检查

用于在流程中监听终止条件。支持同步与异步两种模式，走向值可控制异常抛出，`consume_at` 可控制消费时机。

### 同步模式字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `abort_text` | str 或 list 或 dict | 必填 | 终止关键词规则 |
| `on_match` | str | `break_outer` | 命中走向 |
| `on_miss` | str | `next` | 未命中走向 |
| `exact` | bool | `defaults.exact` | 是否精确匹配 |
| `retry` | int | `defaults.retry` | 重试次数 |
| `retry_interval` | float | `defaults.retry_interval` | 重试间隔 |
| `region` | [x1,y1,x2,y2] | - | 限定区域 |
| `coords` | [x,y] | - | 配合 `region_size` 等生成区域 |
| `region_size` | float | - | 以 `coords` 为中心的方形区域边长 |
| `region_w` | float | `region_size` 或 200 | 区域宽 |
| `region_h` | float | `region_size` 或 200 | 区域高 |

### 异步模式字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `async` | bool | false | 为 true 时启动后台监听线程 |
| `abort_text` | str 或 list 或 dict | 必填 | 终止关键词规则 |
| `on_match` | str | `break_outer` | 命中走向 |
| `retry_interval` | float | `defaults.retry_interval` | 轮询间隔 |
| `consume_at` | str | `step` | `step` 立即消费，`loop_end` 循环结束消费，`outer_end` 外层坐标项结束消费 |
| `not_confirm_count` | int | 3 | 仅 `not` 规则命中时需连续确认次数 |
| `exact` | bool | `defaults.exact` | 是否精确匹配 |
| `region` | [x1,y1,x2,y2] | - | 限定区域 |
| `coords` | [x,y] | - | 配合 `region_size` 等生成区域 |
| `region_size` | float | - | 以 `coords` 为中心的方形区域边长 |
| `region_w` | float | `region_size` 或 200 | 区域宽 |
| `region_h` | float | `region_size` 或 200 | 区域高 |

### 走向值

| 走向值 | 抛出异常 | 捕获者 | 效果 |
|---|---|---|---|
| `break_outer` | `SkillAbort` | `for_each_coord` | 跳到下一个坐标项 |
| `break_inner` | `LoopBreak` | `repeat` 或 `for_each_coord` 内循环 | 跳出当前循环 |
| `next` | 无 | - | 继续下一步 |

### consume_at 取值

| consume_at | 消费时机 |
|---|---|
| `step` | 每步开始（`run_step` 入口 / click / wait 分片 / repeat 每轮） |
| `loop_end` | `repeat` 每轮结束 |
| `outer_end` | `for_each_coord` 每个坐标项内循环结束 |

### 异步同配置复用

异步线程通过 signature 比较，配置不变时复用现有线程，避免 `repeat` 每轮重启导致 `not_confirm_count` 计数被重置。

### 示例

```yaml
# 同步
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

# 异步（repeat 内监听满级）
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

# 连续确认（not 规则命中需连续 3 次）
- action: abort_check
  async: true
  abort_text:
    mode: mixed
    rules:
      - type: not
        keywords: ["确定"]
  on_match: break_inner
  consume_at: loop_end
  not_confirm_count: 3
  retry_interval: 0.5
```

---

## 7. `dump_ocr` — 打印 OCR 内容

### 字段

无。

### 行为

调用 `finder.get_page_ocr_data`，逐条打印 `(cx, cy)  「text」  conf=score`。OCR 失败返回 False。

### 示例

```yaml
- action: dump_ocr
```

---

## 8. `repeat` — 固定次数循环

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `times` | int | 1 | 循环次数 |
| `steps` | list | 必填 | 子步骤列表 |

### 行为

循环 `times` 轮，每轮依次 `run_step` 执行 `steps`：

- 子步骤失败：打印警告并返回 False，中断整个 repeat。
- 捕获 `LoopBreak`：打印日志返回 True（跳出 repeat）。
- 每轮开始检查异步终止（`phase=step`），每轮结束检查（`phase=loop_end`）。
- 捕获 `SkillAbort` 会向上传播，由外层 `for_each_coord` 处理。

### 示例

```yaml
- action: repeat
  times: 7
  steps:
    - action: click
      target: coords
      coords: [849, 2282]
    - action: abort_check
      async: true
      abort_text:
        mode: mixed
        rules:
          - type: must
            keywords: ["最高等级"]
      on_match: break_outer
      consume_at: outer_end
    - action: click
      target: coords
      coords: [500, 1682]
```

---

## 9. `for_each_coord` — 遍历坐标列表

遍历坐标列表，每个坐标点击后进入内部循环执行子步骤。

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `coords_list` | list | 必填 | 坐标列表，元素为 `[x,y]` 或 `{coord: [x,y], times: n}` |
| `skill_coords` | list | - | `coords_list` 的别名 |
| `steps` | list | 必填 | 每个坐标下执行的子步骤 |
| `sub_steps` | list | - | `steps` 的别名 |
| `times` | int | 1 | 每个坐标的内部循环次数，可被坐标项 `times` 覆盖 |
| `loop_times` | int | - | `times` 的别名 |
| `click_wait` | float | `defaults.interval` | 点击坐标后的等待 |
| `interval` | float | `defaults.interval` | 每轮内部循环之间的间隔 |
| `close_popup_before_next` | bool | false | 处理下一个坐标前发送返回键关闭弹窗 |
| `global_abort` | dict | - | `{keywords: [...], exact: bool}` 全局终止词 |
| `abort_text` | str 或 list 或 dict | - | 每个坐标点击后自动启动的异步终止监听规则 |
| `on_match` | str | `break_outer` | 异步监听命中走向 |
| `retry_interval` | float | `defaults.retry_interval` | 异步监听轮询间隔 |
| `not_confirm_count` | int | 3 | 异步监听连续确认次数 |
| `exact` | bool | `defaults.exact` | 异步监听是否精确匹配 |

### 行为

1. 校验 `coords_list` 与 `steps` 非空。
2. 若配了 `global_abort`，调 `set_global_abort` 生效；否则清空全局终止词。
3. 遍历每个坐标：
   - 点击坐标 `dm.touch(item_coord)`，等待 `click_wait`。
   - 若配了 `abort_text`，启动异步 `abort_check`（`consume_at=step`）。
   - 内部循环 `item_times` 轮，每轮 `run_step` 执行 `steps`；子步骤失败标记 `item_ok=False` 并跳出。
   - 捕获 `SkillAbort`：提前中止当前坐标项，`item_ok=False`。
   - 捕获 `LoopBreak`：打断内循环，继续下一个坐标。
   - 内循环结束后检查 `phase=outer_end` 的异步命中。
   - 停掉异步线程。
   - 若 `close_between` 且不是最后一个坐标，发送 `keyevent 4` 关闭弹窗。
4. `finally` 中清空全局终止词并停止异步线程。
5. 返回 `all_ok`，所有坐标项都成功才 True。

### 示例

```yaml
- action: for_each_coord
  remark: "对技能 1~6 依次执行"
  click_wait: 0.5
  coords_list:
    - [294, 895]
    - [540, 895]
    - {coord: [798, 911], times: 10}
  times: 7
  interval: 0.3
  close_popup_before_next: false
  global_abort:
    keywords: ["网络异常"]
    exact: false
  steps:
    - action: click
      target: last
      times: 1
    - action: click
      target: coords
      coords: [531, 1775]
      times: 2

# 带自动异步终止监听
- action: for_each_coord
  coords_list:
    - [294, 895]
    - [540, 895]
  abort_text:
    mode: mixed
    rules:
      - type: must
        keywords: ["最高等级"]
  on_match: break_outer
  retry_interval: 0.3
  not_confirm_count: 3
  steps:
    - action: click
      target: coords
      coords: [849, 2282]
```

---

## 10. `poll_click` — 轮询点击

调用 `PollClicker`，反复点同一坐标（或坐标列表），直到页面出现或消失指定文本。

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `coords` | [x,y] | - | 单坐标模式 |
| `coords_list` | list | - | 多坐标模式，优先于 `coords` |
| `start_text` | str | - | 2×2 区域推算：区域起点及左右分界 |
| `end_text` | str | - | 2×2 区域推算：区域终点 |
| `expect_text` | str 或 list 或 dict | `"升级"` | 页面期望文本，用于判断弹窗是否打开 |
| `click_text` | str | `"升级"` | 弹窗内实际点击的文本 |
| `times` | int | 20 | 每个坐标最大重试次数 |
| `interval` | float | `defaults.interval` | 每次成功点击后的间隔 |
| `sleep` | float | `defaults.sleep` | 完成后休眠 |

### 行为

按 `coords_list`、`coords`、`locate_coords()`（由 `start_text` 和 `end_text` 推算）的优先级取坐标，逐个坐标轮询点击，直到 `expect_text` 消失或达到 `max_times`。完成后打印统计：处理坐标数、完成数、成功点击数、错误数。

### 示例

```yaml
- action: poll_click
  coords_list:
    - [389, 1328]
    - [895, 1313]
  expect_text: "升级"
  click_text: "升级"
  times: 20
  interval: 1.0

# 由起止文本自动推算 2×2 坐标
- action: poll_click
  start_text: "常规技能"
  end_text: "技能结束"
  expect_text: "升级"
  click_text: "升级"
  times: 20
  interval: 1.0
```

---

## 11. `call_flow` — 调用子流程

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `flow` | str | 必填 | 子流程名，对应 `config/flows/<name>.yaml` 文件名 |
| `before` | list | - | 前置动作列表 |
| `after` | list | - | 后置动作列表 |
| `times` | int | 子流程 `loop_count` 或 1 | 主体循环次数 |

### 行为

1. 校验 `flow` 存在，否则报错返回 False。
2. 检查循环引用：`flow` 在 `_include_stack` 中则报错返回 False。
3. `_include_stack` 压入 `flow`。
4. 执行 `before` 子步骤，失败返回 False。
5. 执行子流程 `steps`，循环 `times` 次，任一轮失败返回 False。
6. 执行 `after` 子步骤，失败返回 False。
7. `finally` 中弹出 `_include_stack`。

### 示例

```yaml
- action: call_flow
  flow: 将领技能强化
  before:
    - action: click
      target: coords
      coords: [278, 355]
  after:
    - action: wait
      seconds: 1.0
```

---

## 12. `run_method` — 调用业务方法

调用 `core/flows/` 中注册的业务方法。

### 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `method` | str | 必填 | 方法名，registry 中的 key |
| `params` | dict | {} | 传给方法的 kwargs |
| `store` | str | - | 结果存到 `_action_data[store]` |

### 行为

1. 从 registry 查找 `method`；找不到则尝试 `ActionRunner` 的同名方法；都没有则报错返回 False。
2. `params` 必须是 dict，否则报错返回 False。
3. 调用 `method(**params)`：
   - 捕获 `LoopBreak` 或 `SkillAbort` 直接抛出，让外层处理。
   - 其他异常打印堆栈返回 False。
4. 若配了 `store`：结果存到 `_action_data[store]`，打印项数。
5. 未配 `store` 且方法名不以 `save_`、`write_`、`update_` 开头：提示返回值未保留。

### 示例

```yaml
- action: run_method
  remark: "扫描将领技能等级"
  method: scan_general_skills
  store: data
  params:
    general_coord: [482, 320]
    pattern: "[Ll][Vv]\\.?\\s*(\\d+)\\s*/\\s*(\\d+)"
    file: "data/general_plan.json"

- action: run_method
  remark: "保存建筑升级信息"
  method: save_upgrade_building_info
  params:
    file: data/upgrade_building_info.json
  enabled: true
```

---

## 附：动作速查表

| action | 一句话 | 典型场景 |
|---|---|---|
| `find` | 查找文本存坐标 | 找「确定」再点 |
| `click` | 点击 | 固定坐标连点 |
| `find_click` | 查找并点击 | 找「升级」点击，带缓存 |
| `wait` | 等待秒数 | 弹窗动画等待 |
| `wait_text` | 等文本出现 | 等「升级成功」 |
| `abort_check` | 终止监听 | 检测「最高等级」跳下一技能 |
| `dump_ocr` | 打印页面 OCR | 调试 |
| `repeat` | 固定循环 | 精工 7 轮 |
| `for_each_coord` | 遍历坐标 | 6 个技能依次处理 |
| `poll_click` | 轮询点击 | 技能升级到点满 |
| `call_flow` | 调子流程 | 组合「强化加精工」 |
| `run_method` | 调业务方法 | 保存建筑或邮件信息 |
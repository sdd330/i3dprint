<script setup>
// 进阶手动参数 —— OrcaSlicer Process Settings 全分组（wiki 对齐）
// 默认值 = Bambu Lab X1 Carbon 标准档基准（x1c_standard_full.json）
// 「自动」提示项：0/auto 由切片器自动计算（如线宽=0、加速度=auto、悬垂分级速度）
import { computed } from 'vue'

const props = defineProps({ modelValue: { type: Object, default: () => ({}) } })
const emit = defineEmits(['update:modelValue'])
const m = computed(() => props.modelValue)
const set = (k, v) => emit('update:modelValue', { ...props.modelValue, [k]: v })

const GROUPS = [
  {
    name: '质量 Quality', icon: '🎯', items: [
      { k: 'layer_height', label: '层高', type: 'num', min: 0.04, max: 0.5, step: 0.04, unit: 'mm' },
      { k: 'initial_layer_print_height', label: '首层层高', type: 'num', min: 0.08, max: 1, step: 0.04, unit: 'mm' },
      { k: 'line_width', label: '线宽（0=自动）', type: 'num', min: 0, max: 1.2, step: 0.05, unit: 'mm', hint: '0 = 按喷嘴×系数自动' },
      { k: 'seam_position', label: '接缝位置', type: 'select', options: ['aligned', 'nearest', 'random', 'back', 'spiral'] },
      { k: 'wall_generator', label: '壁生成器', type: 'select', options: ['classic', 'arachne'] },
      { k: 'ironing_type', label: '熨平', type: 'select', options: ['no ironing', 'top', 'all'] },
      { k: 'ironing_speed', label: '熨平速度', type: 'num', min: 10, max: 200, step: 5, unit: 'mm/s' },
    ],
  },
  {
    name: '强度 Strength', icon: '🏗️', items: [
      { k: 'wall_loops', label: '壁厚圈数', type: 'num', min: 1, max: 8, step: 1, unit: '圈' },
      { k: 'top_shell_layers', label: '顶实心层', type: 'num', min: 0, max: 12, step: 1, unit: '层' },
      { k: 'bottom_shell_layers', label: '底实心层', type: 'num', min: 0, max: 12, step: 1, unit: '层' },
      { k: 'infill_density', label: '填充率', type: 'num', min: 0, max: 100, step: 5, unit: '%' },
      { k: 'infill_pattern', label: '填充图案', type: 'select', options: ['grid', 'gyroid', 'cubic', 'lines', 'triangles', 'adaptive cubic', 'cross', 'lightning'] },
    ],
  },
  {
    name: '速度 Speed', icon: '⚡', items: [
      { k: 'initial_layer_speed', label: '首层速度', type: 'num', min: 10, max: 120, step: 5, unit: 'mm/s' },
      { k: 'outer_wall_speed', label: '外壁速度', type: 'num', min: 20, max: 400, step: 10, unit: 'mm/s' },
      { k: 'inner_wall_speed', label: '内壁速度', type: 'num', min: 20, max: 400, step: 10, unit: 'mm/s' },
      { k: 'top_surface_speed', label: '顶面速度', type: 'num', min: 20, max: 400, step: 10, unit: 'mm/s' },
      { k: 'internal_solid_infill_speed', label: '实心填充速度', type: 'num', min: 20, max: 400, step: 10, unit: 'mm/s' },
      { k: 'sparse_infill_speed', label: '稀疏填充速度', type: 'num', min: 20, max: 400, step: 10, unit: 'mm/s' },
      { k: 'bridge_speed', label: '桥接速度', type: 'num', min: 10, max: 200, step: 5, unit: 'mm/s' },
      { k: 'travel_speed', label: '空驶速度', type: 'num', min: 100, max: 600, step: 10, unit: 'mm/s' },
      { k: 'enable_overhang_speed', label: '悬垂降速', type: 'bool', hint: '开启后按角度自动分级（软件计算）' },
      { k: 'overhang_2_4_speed', label: '悬垂 2/4 速度（0=自动）', type: 'num', min: 0, max: 200, step: 5, unit: 'mm/s' },
      { k: 'default_acceleration', label: '默认加速度（auto=自动）', type: 'num', min: 0, max: 30000, step: 500, unit: 'mm/s²', hint: '0/auto = 机器自动' },
      { k: 'initial_layer_acceleration', label: '首层加速度', type: 'num', min: 0, max: 30000, step: 500, unit: 'mm/s²' },
      { k: 'outer_wall_acceleration', label: '外壁加速度', type: 'num', min: 0, max: 30000, step: 500, unit: 'mm/s²' },
      { k: 'travel_acceleration', label: '空驶加速度', type: 'num', min: 0, max: 30000, step: 500, unit: 'mm/s²' },
    ],
  },
  {
    name: '温度 Temperature', icon: '🌡️', items: [
      { k: 'nozzle_temperature', label: '喷嘴温度', type: 'num', min: 180, max: 300, step: 5, unit: '°C' },
      { k: 'initial_layer_print_temperature', label: '首层喷嘴温度', type: 'num', min: 180, max: 300, step: 5, unit: '°C' },
      { k: 'bed_temperature', label: '热床温度', type: 'num', min: 20, max: 120, step: 5, unit: '°C' },
      { k: 'initial_layer_bed_temperature', label: '首层热床温度', type: 'num', min: 20, max: 120, step: 5, unit: '°C' },
    ],
  },
  {
    name: '支撑 Support', icon: '🛠️', items: [
      { k: 'enable_support', label: '启用支撑', type: 'bool' },
      { k: 'support_type', label: '支撑类型', type: 'select', options: ['normal(auto)', 'tree(auto)', 'normal', 'tree'] },
      { k: 'support_threshold_angle', label: '支撑角度阈值', type: 'num', min: 0, max: 90, step: 5, unit: '°' },
      { k: 'support_interface_pattern', label: '接触面图案', type: 'select', options: ['auto', 'lines', 'grid'] },
      { k: 'support_base_pattern', label: '支撑基座图案', type: 'select', options: ['default', 'rectilinear', 'triangles', 'honeycomb'] },
      { k: 'support_speed', label: '支撑速度', type: 'num', min: 20, max: 300, step: 10, unit: 'mm/s' },
      { k: 'support_interface_speed', label: '接触面速度', type: 'num', min: 20, max: 200, step: 10, unit: 'mm/s' },
      { k: 'raft_layers', label: '筏层数（0=无）', type: 'num', min: 0, max: 5, step: 1, unit: '层' },
    ],
  },
  {
    name: '平台附加 Others', icon: '📏', items: [
      { k: 'brim_type', label: '底边类型', type: 'select', options: ['auto_brim', 'no_brim', 'brim', 'outer_brim', 'mouse_ear'] },
      { k: 'brim_width', label: '底边宽度', type: 'num', min: 0, max: 40, step: 1, unit: 'mm' },
      { k: 'skirt_loops', label: '裙边圈数', type: 'num', min: 0, max: 10, step: 1, unit: '圈' },
      { k: 'fuzzy_skin_thickness', label: '绒毛厚度（0=关）', type: 'num', min: 0, max: 1, step: 0.05, unit: 'mm' },
      { k: 'scan_first_layer', label: '首层激光扫描（拓竹校准）', type: 'bool', hint: 'X1C 激光雷达首层流量扫描；关闭可提速但失去自动流量校准' },
    ],
  },
  {
    name: '高级 Advanced', icon: '🧰', items: [
      { k: 'retraction_length', label: '回抽长度', type: 'num', min: 0, max: 10, step: 0.1, unit: 'mm' },
      { k: 'retraction_speed', label: '回抽速度', type: 'num', min: 20, max: 100, step: 5, unit: 'mm/s' },
      { k: 'z_hop', label: 'Z 抬升', type: 'num', min: 0, max: 2, step: 0.1, unit: 'mm' },
      { k: 'max_volumetric_speed', label: '最大体积速度', type: 'num', min: 1, max: 40, step: 1, unit: 'mm³/s', hint: '由材料校准决定，通常勿动' },
      { k: 'elephant_foot_compensation', label: '大象脚补偿', type: 'num', min: 0, max: 1, step: 0.05, unit: 'mm' },
      { k: 'xy_hole_compensation', label: '孔位补偿(XY)', type: 'num', min: -1, max: 1, step: 0.05, unit: 'mm' },
    ],
  },
]
</script>

<template>
  <div>
    <div v-for="g in GROUPS" :key="g.name" style="margin-bottom: 16px">
      <div style="font-weight: 700; font-size: 13px; margin-bottom: 6px; display: flex; align-items: center; gap: 6px">
        <span>{{ g.icon }}</span>{{ g.name }}
        <span class="muted" style="font-weight: 400; font-size: 11.5px">（OrcaSlicer 同字段）</span>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px">
        <div v-for="it in g.items" :key="it.k">
          <div class="muted" style="font-size: 12px; margin-bottom: 2px">
            {{ it.label }}<span v-if="it.unit" style="margin-left: 4px">({{ it.unit }})</span>
            <el-tooltip v-if="it.hint" :content="it.hint" placement="top">
              <span style="color: var(--blue); cursor: help">ⓘ</span>
            </el-tooltip>
          </div>
          <el-input-number v-if="it.type === 'num'" :model-value="Number(m[it.k] ?? 0)" :min="it.min" :max="it.max" :step="it.step"
                           size="small" style="width: 100%" @update:model-value="v => set(it.k, v)" />
          <el-select v-else-if="it.type === 'select'" :model-value="String(m[it.k] ?? '')" size="small" style="width: 100%"
                     @update:model-value="v => set(it.k, v)">
            <el-option v-for="o in it.options" :key="o" :value="o" :label="o" />
          </el-select>
          <el-switch v-else :model-value="!!m[it.k] && m[it.k] !== '0'" @update:model-value="v => set(it.k, v ? '1' : '0')" />
        </div>
      </div>
    </div>
  </div>
</template>

# Kids Mind 视觉系统设计系统 v1.0

已按《视觉系统设计需求清单》完成 D1–D8、D10 交付物，D9 切图导出包建议用 Figma/Sketch 批量导出。

## 文件结构

```
kids-mind-design-system/
├── index.html              # 总览 + 交付清单 + 动效 + 无障碍
├── tokens.html             # 色彩、字体、间距、圆角、阴影、医疗风险色
├── icons.html              # 约 50 枚 24px 线性圆角图标 + SVG Sprite
├── components.html         # 按钮 / 输入 / 卡片 / 标签 / 弹窗 / Toast / 风险卡片 / 时间线 / 导航
├── pages.html              # 6 个模块页面视觉稿（桌面 1440 + 移动 390）
├── illustrations.html        # 水彩绘本风参考图 + AI 提示词模板 + 导出规格
├── assets/
│   ├── tokens.css          # CSS 变量
│   ├── tokens.json         # JSON Token
│   ├── styles.css          # 公共样式
│   ├── icons.svg           # SVG Sprite（已内联到使用页面）
│   └── illustrations/      # 3 张 AI 生成参考图
└── preview-*.png           # 页面渲染预览
```

## 关键设计决策

- **品牌标识**：沿用已确认的「心智萌芽」Logo，字标全小写 Quicksand。
- **色彩**：主色刷新为陶土橙 #D86B4C；保留现有暖米底 #F5F2EC；医疗风险单独色板并强制配图标。
- **字体**：中文标题/正文改用思源黑体 / 阿里巴巴普惠体，避免 Windows 降级为 SimSun。
- **深色模式**：当前版本暂不支持，Token 命名已预留扩展空间。
- **动效**：仅使用 transform/opacity，支持 prefers-reduced-motion 降级。

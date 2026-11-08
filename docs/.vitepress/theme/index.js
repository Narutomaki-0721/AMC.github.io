import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import AtlasHome from './AtlasHome.vue'
import TaskBoard from './TaskBoard.vue'
import ChatDock from './ChatDock.vue'
import './style.css'
export default {extends:DefaultTheme,Layout:()=>h(DefaultTheme.Layout,null,{'layout-bottom':()=>h(ChatDock)}),
  enhanceApp({app}) {app.component('AtlasHome',AtlasHome);app.component('TaskBoard',TaskBoard)}}

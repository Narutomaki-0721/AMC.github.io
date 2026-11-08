<script setup>
import { useData, withBase } from 'vitepress'
const {theme} = useData()
</script>
<template><main class="atlas"><div class="mast"><div class="mark" aria-hidden="true">∑</div><div><p class="eyebrow">MCM / ICM</p><h1>备赛知识目录</h1></div></div>
<section class="shelves"><details v-for="g in theme.sidebar" :key="g.text" open><summary>{{g.text}}</summary><ul><li v-for="item in g.items" :key="item.text"><a v-if="item.link" :href="withBase(item.link+'.html')">{{item.text}}</a><template v-else>{{item.text}}<ul><li v-for="sub in item.items" :key="sub.link"><a :href="withBase(sub.link+'.html')">{{sub.text}}</a></li></ul></template></li></ul></details></section>
<a class="tasklink" :href="withBase('/tasks.html')">查看团队任务流 →</a></main></template>

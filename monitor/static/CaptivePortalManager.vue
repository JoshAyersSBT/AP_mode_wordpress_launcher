<template>
  <div class="portal-manager">
    <h2>Captive Portal Editor</h2>

    <input type="file" multiple @change="handleUpload" />
    <button @click="submitFiles">Upload Files</button>
    <button @click="restoreDefault">Restore Default</button>

    <ul>
      <li v-for="file in fileList" :key="file">
        {{ file }}
        <button @click="previewFile(file)">Preview</button>
      </li>
    </ul>

    <div v-if="previewContent">
      <h3>Preview:</h3>
      <pre>{{ previewContent }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const fileList = ref([])
const previewContent = ref('')
const filesToUpload = ref([])

const fetchFiles = async () => {
  const res = await axios.get('/api/captive-portal/list')
  fileList.value = res.data.files
}

const handleUpload = (e) => {
  filesToUpload.value = Array.from(e.target.files)
}

const submitFiles = async () => {
  const formData = new FormData()
  filesToUpload.value.forEach(file => formData.append('files', file))
  await axios.post('/api/captive-portal/upload', formData)
  fetchFiles()
}

const previewFile = async (filename) => {
  const res = await axios.get(`/api/captive-portal/preview?file=${filename}`)
  previewContent.value = res.data.content
}

const restoreDefault = async () => {
  await axios.post('/api/captive-portal/restore-default')
  fetchFiles()
}

onMounted(fetchFiles)
</script>

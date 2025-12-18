import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const listGlossaries = async () => {
  const response = await api.get('/glossaries');
  return response.data;
};

export const getGlossaryContent = async (glossaryName) => {
  const response = await api.get(`/glossary/${glossaryName}/content`);
  return response.data;
};

export const getPrompt = async () => {
  const response = await api.get('/prompt');
  return response.data;
};

export const detectLanguage = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await axios.post(`${API_BASE_URL}/detect-language`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const startTranslation = async (file, options) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_lang', options.source_lang || 'fr');
  const targetLangValue = options.target_lang || 'it';
  formData.append('target_lang', targetLangValue);
  formData.append('use_glossary', options.use_glossary !== false);
  formData.append('skip_memory', options.skip_memory !== false);
  
  if (options.reference_doc) {
    formData.append('reference_doc', options.reference_doc);
  }
  
  if (options.custom_prompt) {
    formData.append('custom_prompt', options.custom_prompt);
  }

  const response = await axios.post(`${API_BASE_URL}/translate`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const getTranslationStatus = async (jobId) => {
  const response = await api.get(`/translate/${jobId}/status`);
  return response.data;
};

export const downloadTranslation = async (jobId) => {
  const url = `/translate/${jobId}/download`;
  
  try {
    // Use api instance instead of axios directly to get /api prefix automatically
    const response = await api.get(url, {
      responseType: 'blob',
    });
    
    // Check if response is HTML (error page)
    if (response.headers['content-type']?.includes('text/html')) {
      const text = await response.data.text();
      throw new Error('Server returned HTML instead of PDF. Check URL and endpoint.');
    }
    
    // Create download link
    const url_blob = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url_blob;
    link.setAttribute('download', `translated_${jobId}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url_blob);
  } catch (error) {
    throw error;
  }
};

export const cancelTranslation = async (jobId) => {
  const response = await api.post(`/translate/${jobId}/cancel`);
  return response.data;
};

export const getTranslationReport = async (jobId) => {
  const response = await api.get(`/translate/${jobId}/report`);
  return response.data;
};

export const downloadTranslatedText = async (jobId) => {
  // Use api instance for consistency
  const response = await api.get(`/translate/${jobId}/text`, {
    responseType: 'blob',
  });
  
  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/plain' }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `translated_${jobId}.txt`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};


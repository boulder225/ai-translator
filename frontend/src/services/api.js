import axios from 'axios';

const API_BASE_URL = '/api';

// Helper to get user role from localStorage
const getUserRoleFromStorage = () => {
  return localStorage.getItem('userRole') || '';
};

// Helper to get username from localStorage
const getUsername = () => {
  return localStorage.getItem('username') || '';
};

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include user role and username in headers
api.interceptors.request.use(
  (config) => {
    const userRole = getUserRoleFromStorage();
    const username = getUsername();
    
    if (userRole) {
      config.headers['X-User-Role'] = userRole;
    }
    if (username) {
      config.headers['X-Username'] = username;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export const listGlossaries = async () => {
  const response = await api.get('/glossaries');
  return response.data;
};

export const getGlossaryContent = async (glossaryName) => {
  const response = await api.get(`/glossary/${glossaryName}/content`);
  return response.data;
};

export const updateGlossaryContent = async (glossaryName, entries) => {
  const response = await api.put(`/glossary/${glossaryName}/content`, {
    entries: entries
  });
  return response.data;
};

export const getUserRole = async (username) => {
  // Create a temporary request without using the interceptor (to avoid circular dependency)
  const response = await axios.get('/api/user-role', {
    headers: {
      'X-Username': username,
    },
  });
  return response.data;
};

export const getPrompt = async () => {
  // Include user role headers for admin check
  const userRole = getUserRoleFromStorage();
  const username = getUsername();
  
  const response = await api.get('/prompt', {
    headers: {
      'X-User-Role': userRole,
      'X-Username': username,
    },
  });
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
  // TranslationForm passes skip_memory: !useMemory (already correct)
  // skip_memory: true means skip, false means use memory
  // Pass it through directly (TranslationForm always provides it)
  formData.append('skip_memory', options.skip_memory ?? false);
  formData.append('preserve_formatting', options.preserve_formatting ?? false);

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

export const startTranslationStreaming = async (file, options, onChunk, onComplete, onError) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_lang', options.source_lang || 'fr');
  formData.append('target_lang', options.target_lang || 'it');
  formData.append('use_glossary', options.use_glossary !== false);
  formData.append('skip_memory', options.skip_memory ?? false);
  formData.append('preserve_formatting', options.preserve_formatting ?? false);

  if (options.reference_doc) {
    formData.append('reference_doc', options.reference_doc);
  }

  if (options.custom_prompt) {
    formData.append('custom_prompt', options.custom_prompt);
  }

  try {
    const userRole = getUserRoleFromStorage();
    const username = getUsername();

    const response = await fetch(`${API_BASE_URL}/translate-stream`, {
      method: 'POST',
      body: formData,
      headers: {
        'X-User-Role': userRole || '',
        'X-Username': username || '',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));

          if (data.type === 'chunk' && onChunk) {
            onChunk(data.text);
          } else if (data.type === 'done' && onComplete) {
            onComplete(data.full_text, data.message, data.stats, data.session_id);
          } else if (data.type === 'error') {
            throw new Error(data.message);
          }
        }
      }
    }
  } catch (error) {
    if (onError) {
      onError(error);
    } else {
      throw error;
    }
  }
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

export const downloadStreamingPdf = async (sessionId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/translate-stream/${sessionId}/download`, {
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
    link.setAttribute('download', `translated_streaming.pdf`);
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

export const getMemoryContent = async () => {
  const response = await api.get('/memory/content');
  return response.data;
};

export const updateMemoryContent = async (entries) => {
  const response = await api.put('/memory/content', { entries });
  return response.data;
};

export const deleteAllMemoryContent = async () => {
  const response = await api.delete('/memory/content');
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


export const exportTranslationMemoryTMX = async (jobId) => {
  const response = await api.get(`/translate/${jobId}/export/tmx`, {
    responseType: 'blob',
  });
  
  // Extract filename from Content-Disposition header or use default
  const contentDisposition = response.headers['content-disposition'];
  let filename = `translation_memory_${jobId}.tmx`;
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }
  
  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/xml' }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const exportGlossaryTBX = async (jobId) => {
  const response = await api.get(`/translate/${jobId}/export/tbx`, {
    responseType: 'blob',
  });
  
  // Extract filename from Content-Disposition header or use default
  const contentDisposition = response.headers['content-disposition'];
  let filename = `glossary_${jobId}.tbx`;
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }
  
  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/xml' }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

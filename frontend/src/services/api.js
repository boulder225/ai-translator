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

export const getMemoryContent = async () => {
  const response = await api.get('/memory/content');
  return response.data;
};

export const updateMemoryContent = async (entries) => {
  const response = await api.put('/memory/content', { entries });
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


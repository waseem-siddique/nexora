try{document.documentElement.dataset.theme=localStorage.getItem('nexora-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){}

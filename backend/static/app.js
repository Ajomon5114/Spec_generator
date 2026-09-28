const { createApp, ref, onMounted, watch, computed } = Vue;

const app = createApp({
    setup() {
        const specData = ref(null);
        const templates = ref([]);
        const isGenerating = ref(false);
        const isParsing = ref(false);
        const pdfUrl = ref(null);
        const viewMode = ref('edit'); // 'edit' or 'preview'
        const activeRoute = ref('home'); // 'home' or 'generator'
        
        const availableProtocols = ref([]);
        const isSavingSettings = ref(false);
        const pdfInput = ref(null);

        // User & Activity Management
        const users = ref([]);
        const activityLogs = ref([]);
        const showNewUserModal = ref(false);
        const newUser = ref({ username: '', password: '', role: 'user' });

        const currentUser = ref(null);
        const dashboardStats = ref({ total_templates: 0, total_users: 0, recent_templates: [] });
        
        const searchQuery = ref('');
        const filteredTemplates = computed(() => {
            if (!searchQuery.value) return templates.value;
            const q = searchQuery.value.toLowerCase();
            return templates.value.filter(t => 
                t.product_name.toLowerCase().includes(q) || 
                (t.spec_data && t.spec_data.spec_number && t.spec_data.spec_number.toLowerCase().includes(q))
            );
        });

        // Check Auth and Fetch DB templates
        const loadData = async () => {
            try {
                // Check auth
                const meRes = await fetch('/api/me');
                if (!meRes.ok) {
                    window.location.href = '/login';
                    return;
                }
                currentUser.value = await meRes.json();

                if (currentUser.value.role === 'dept_head' && !new URLSearchParams(window.location.search).get('route')) {
                    activeRoute.value = 'settings';
                }
                
                // Fetch stats initially if on home
                if (activeRoute.value === 'home') {
                    loadDashboardStats();
                }

                // Fetch templates
                const response = await fetch('/api/templates?t=' + new Date().getTime());
                const data = await response.json();
                templates.value = data.templates || [];
                
                // Fetch Settings
                const settingsRes = await fetch('/api/settings?t=' + new Date().getTime());
                const settingsData = await settingsRes.json();
                if (settingsData.settings && settingsData.settings.protocols) {
                    availableProtocols.value = settingsData.settings.protocols;
                }

                // On initial load, set default data
                if (templates.value.length > 0 && !specData.value) {
                    const defaultSpec = JSON.parse(JSON.stringify(templates.value[0].spec_data));
                    defaultSpec.product_name = templates.value[0].product_name;
                    specData.value = defaultSpec;
                } else if (!specData.value) {
                    specData.value = {
                        product_name: "New Product",
                        spec_number: "", effective_date: "", botanical_name: "", plant_part_used: "",
                        standardization: "", production_method: "", shelf_life: "", country_of_origin: "",
                        test_categories: [], additional_info: []
                    };
                }
            } catch (err) {
                console.error('Failed to load data', err);
            }
        };

        const handleLogout = async () => {
            await fetch('/api/logout', { method: 'POST' });
            window.location.href = '/login';
        };

        onMounted(() => {
            const params = new URLSearchParams(window.location.search);
            if (params.get('route')) {
                activeRoute.value = params.get('route');
            }
            loadData();
        });

        const clearNewFlags = (data) => {
            if (data && data.test_categories) {
                data.test_categories.forEach(cat => {
                    if (cat.rows) cat.rows.forEach(r => delete r.isNew);
                });
            }
            if (data && data.additional_info) {
                data.additional_info.forEach(info => delete info.isNew);
            }
        };

        watch(() => specData.value?.product_name, (newVal) => {
            if (!newVal) return;
            const foundTemplate = templates.value.find(t => t.product_name === newVal);
            if (foundTemplate && foundTemplate.spec_data) {
                const newSpec = JSON.parse(JSON.stringify(foundTemplate.spec_data));
                newSpec.product_name = newVal;
                newSpec.id = foundTemplate.id; // ensure ID is present for saving
                clearNewFlags(newSpec);
                specData.value = newSpec;
            }
        });

        // Form operations
        const addCategory = () => {
            const catName = prompt("Enter the name for the new category:", "New Category");
            if (catName !== null && catName.trim() !== "") {
                specData.value.test_categories.push({
                    category: catName.trim(),
                    rows: [
                        { sl_no: '', protocol: '', parameter: '', limit: '', isNew: true }
                    ]
                });
            }
        };

        const removeCategory = (idx) => {
            if (confirm("Are you sure you want to remove this entire category?")) {
                specData.value.test_categories.splice(idx, 1);
                recalculateSlNos();
            }
        };

        const addTestRow = (catIdx) => {
            specData.value.test_categories[catIdx].rows.push({
                sl_no: '', protocol: '', parameter: '', limit: '', isNew: true
            });
        };

        const removeTestRow = (catIdx, rowIdx) => {
            specData.value.test_categories[catIdx].rows.splice(rowIdx, 1);
            recalculateSlNos();
        };
        const duplicateTestRow = (catIdx, rowIdx) => {
            const rowToCopy = specData.value.test_categories[catIdx].rows[rowIdx];
            const copiedRow = JSON.parse(JSON.stringify(rowToCopy));
            copiedRow.isNew = true; // Mark as new so it's editable
            specData.value.test_categories[catIdx].rows.splice(rowIdx + 1, 0, copiedRow);
        };

        const updateSlNos = (changedCatIdx, changedRowIdx) => {
            const changedRow = specData.value.test_categories[changedCatIdx].rows[changedRowIdx];
            let currentSlNo = parseInt(changedRow.sl_no, 10);
            
            if (isNaN(currentSlNo)) return;

            let foundChanged = false;

            for (let i = 0; i < specData.value.test_categories.length; i++) {
                const cat = specData.value.test_categories[i];
                for (let j = 0; j < cat.rows.length; j++) {
                    const row = cat.rows[j];
                    
                    if (i === changedCatIdx && j === changedRowIdx) {
                        foundChanged = true;
                        continue;
                    }

                    if (foundChanged) {
                        if (row.sl_no && row.sl_no.trim() !== '') {
                            currentSlNo++;
                            row.sl_no = currentSlNo.toString();
                        }
                    }
                }
            }
        };

        const recalculateSlNos = () => {
            let currentSlNo = null;

            for (let i = 0; i < specData.value.test_categories.length; i++) {
                const cat = specData.value.test_categories[i];
                for (let j = 0; j < cat.rows.length; j++) {
                    const row = cat.rows[j];
                    
                    if (row.sl_no && row.sl_no.trim() !== '') {
                        if (currentSlNo === null) {
                            currentSlNo = parseInt(row.sl_no, 10);
                            if (isNaN(currentSlNo)) {
                                currentSlNo = null;
                            }
                        } else {
                            currentSlNo++;
                            row.sl_no = currentSlNo.toString();
                        }
                    }
                }
            }
        };

        const addInfoRow = () => {
            specData.value.additional_info.push({
                parameter: '', detail: '', isNew: true
            });
        };

        const removeInfoRow = (idx) => {
            specData.value.additional_info.splice(idx, 1);
        };
        
        const duplicateInfoRow = (idx) => {
            const rowToCopy = specData.value.additional_info[idx];
            const copiedRow = JSON.parse(JSON.stringify(rowToCopy));
            copiedRow.isNew = true; // Mark as new so it's editable
            specData.value.additional_info.splice(idx + 1, 0, copiedRow);
        };

        // Generate PDF
        const generatePDF = async (downloadFlag = false) => {
            if (!specData.value.product_name || specData.value.product_name.trim() === '') {
                alert("Product Name is required before generating the PDF.");
                return;
            }
            if (!specData.value.spec_number || specData.value.spec_number.trim() === '') {
                alert("Specification Number is required before generating the PDF.");
                return;
            }

            clearNewFlags(specData.value);
            isGenerating.value = true;

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(specData.value)
                });

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }

                const blob = await response.blob();

                if (pdfUrl.value) {
                    window.URL.revokeObjectURL(pdfUrl.value);
                }

                pdfUrl.value = window.URL.createObjectURL(blob);
                if (downloadFlag) {
                    const link = document.createElement('a');
                    link.href = pdfUrl.value;
                    const productName = specData.value.product_name || 'Document';
                    link.download = `${productName} specification.pdf`;
                    link.click();
                } else {
                    viewMode.value = 'preview';
                }
            } catch (error) {
                console.error("Error generating PDF:", error);
                alert("Failed to generate PDF. Check console for details.");
            } finally {
                isGenerating.value = false;
            }
        };

        // Auto-save feature
        let saveTimeout;
        watch(specData, (newVal) => {
            if (!newVal || !newVal.id) return;

            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(async () => {
                try {
                    const payload = {
                        product_name: newVal.product_name,
                        ...newVal
                    };
                    const response = await fetch('/api/save-template', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (response.ok) {
                        console.log("Template auto-saved successfully.");
                    } else {
                        console.error("Auto-save failed with status:", response.status);
                    }
                } catch (err) {
                    console.error("Network error during auto-save:", err);
                }
            }, 1500);
        }, { deep: true });

        const toggleFullScreen = () => {
            const container = document.querySelector('.pdf-container');
            if (!container) return;

            if (!document.fullscreenElement) {
                if (container.requestFullscreen) {
                    container.requestFullscreen();
                } else if (container.webkitRequestFullscreen) {
                    container.webkitRequestFullscreen();
                } else if (container.msRequestFullscreen) {
                    container.msRequestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }
            }
        };

        const createBlankSpec = () => {
            const newSpec = {
                product_name: "",
                spec_number: "", effective_date: "", revision_due_date: "", botanical_name: "", plant_part_used: "",
                standardization: "", production_method: "", shelf_life: "", country_of_origin: "",
                test_categories: [], additional_info: []
            };
            
            specData.value = newSpec;
            activeRoute.value = 'generator';
            viewMode.value = 'edit';
        };

        const triggerPdfUpload = () => {
            if (pdfInput.value) {
                pdfInput.value.click();
            }
        };

        const handlePdfUpload = async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            
            isParsing.value = true;

            try {
                const response = await fetch('/api/parse-pdf', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to parse PDF');
                }

                const data = await response.json();
                if (data.status === 'success' && data.data) {
                    let suggestedName = data.data.product_name || "Parsed PDF Product";
                    let finalName = suggestedName;
                    let counter = 1;
                    
                    while (templates.value.find(t => t.product_name === finalName)) {
                        finalName = `${suggestedName} (${counter})`;
                        counter++;
                    }
                    
                    const newSpec = {
                        product_name: finalName,
                        spec_number: data.data.spec_number || "", 
                        effective_date: data.data.effective_date || "", 
                        revision_due_date: data.data.revision_due_date || "",
                        botanical_name: data.data.botanical_name || "", 
                        plant_part_used: data.data.plant_part_used || "",
                        standardization: data.data.standardization || "", 
                        production_method: data.data.production_method || "", 
                        shelf_life: data.data.shelf_life || "", 
                        country_of_origin: data.data.country_of_origin || "",
                        test_categories: data.data.test_categories || [], 
                        additional_info: data.data.additional_info || []
                    };
                    
                    specData.value = newSpec;
                    activeRoute.value = 'generator';
                    viewMode.value = 'edit';
                    alert("PDF parsed successfully! Please review the extracted data and save.");
                }
            } catch (err) {
                console.error(err);
                alert("Error parsing PDF: " + err.message);
            } finally {
                isParsing.value = false;
                event.target.value = '';
            }
        };

        const editSpec = (t) => {
            specData.value = JSON.parse(JSON.stringify(t.spec_data));
            specData.value.product_name = t.product_name;
            specData.value.id = t.id;
            clearNewFlags(specData.value);
            activeRoute.value = 'generator';
            viewMode.value = 'edit';
        };

        const addProtocol = () => {
            availableProtocols.value.push('');
        };

        const removeProtocol = (idx) => {
            availableProtocols.value.splice(idx, 1);
        };

        const saveSettings = async () => {
            isSavingSettings.value = true;
            try {
                availableProtocols.value = availableProtocols.value.filter(p => p.trim() !== '');
                
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ settings: { protocols: availableProtocols.value } })
                });
                
                if (response.ok) {
                    alert('Settings saved successfully!');
                } else {
                    alert('Failed to save settings');
                }
            } catch (err) {
                console.error(err);
                alert('Error saving settings');
            } finally {
                isSavingSettings.value = false;
            }
        };

        const loadUsers = async () => {
            try {
                const res = await fetch('/api/users');
                if (res.ok) {
                    const data = await res.json();
                    users.value = data.users;
                }
            } catch (e) { console.error(e); }
        };

        const loadActivityLogs = async () => {
            try {
                const res = await fetch('/api/activity-log');
                if (res.ok) {
                    const data = await res.json();
                    activityLogs.value = data.logs;
                }
            } catch (e) { console.error(e); }
        };

        const loadDashboardStats = async () => {
            try {
                const res = await fetch('/api/dashboard-stats');
                if (res.ok) {
                    const data = await res.json();
                    dashboardStats.value = data;
                }
            } catch (e) { console.error(e); }
        };

        watch(activeRoute, (newTab) => {
            if (newTab === 'users') loadUsers();
            else if (newTab === 'activity') loadActivityLogs();
            else if (newTab === 'home') loadDashboardStats();
        });

        const createUser = async () => {
            try {
                const res = await fetch('/api/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newUser.value)
                });
                if (res.ok) {
                    showNewUserModal.value = false;
                    newUser.value = { username: '', password: '', role: 'user' };
                    loadUsers();
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Error creating user');
                }
            } catch (e) { console.error(e); }
        };

        const deleteUser = async (id) => {
            if (!confirm("Are you sure you want to delete this user?")) return;
            try {
                const res = await fetch(`/api/users/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    loadUsers();
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Error deleting user');
                }
            } catch (e) { console.error(e); }
        };

        const changeUserRole = async (user) => {
            try {
                const res = await fetch(`/api/users/${user.id}/role`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role: user.role })
                });
                if (!res.ok) {
                    const data = await res.json();
                    alert(data.detail || 'Error changing role');
                }
            } catch (e) { console.error(e); }
        };

        return {
            specData,
            templates,
            searchQuery,
            filteredTemplates,
            isGenerating,
            isParsing,
            pdfUrl,
            viewMode,
            activeRoute,
            availableProtocols,
            addCategory,
            removeCategory,
            addTestRow,
            removeTestRow,
            duplicateTestRow,
            updateSlNos,
            addInfoRow,
            removeInfoRow,
            duplicateInfoRow,
            generatePDF,
            toggleFullScreen,
            currentUser,
            handleLogout,
            pdfInput,
            createBlankSpec,
            triggerPdfUpload,
            handlePdfUpload,
            editSpec,
            isSavingSettings,
            addProtocol,
            removeProtocol,
            saveSettings,
            users,
            activityLogs,
            showNewUserModal,
            newUser,
            loadActivityLogs,
            createUser,
            deleteUser,
            changeUserRole,
            dashboardStats
        };
    }
});

app.mount('#app');

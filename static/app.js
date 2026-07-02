document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('instance-select');
    const btn = document.getElementById('solve-btn');
    const spinner = document.getElementById('spinner');
    const btnText = btn.querySelector('span');
    const emptyState = document.getElementById('empty-state');
    
    // Stats elements
    const statStatus = document.getElementById('stat-status');
    const statCost = document.getElementById('stat-cost');
    const statGap = document.getElementById('stat-gap');
    const statFes = document.getElementById('stat-fes');
    const statTime = document.getElementById('stat-time');
    const statSimilarity = document.getElementById('stat-similarity');

    // Instance details elements
    const panelDetails = document.getElementById('instance-details-panel');
    const detailCustomers = document.getElementById('detail-customers');
    const detailVehicles = document.getElementById('detail-vehicles');
    const detailCapacity = document.getElementById('detail-capacity');

    // Canvas setup
    const canvas = document.getElementById('cvrp-canvas');
    const ctx = canvas.getContext('2d');
    
    const canvasBks = document.getElementById('bks-canvas');
    const ctxBks = canvasBks.getContext('2d');
    
    const cvrpWrapper = document.getElementById('cvrp-wrapper');
    const bksWrapper = document.getElementById('bks-wrapper');
    const toggleBks = document.getElementById('toggle-bks');
    
    let instancesMap = {};
    let currentAnimationId = null;
    
    // Global State for rendering
    let currentRoutes = null;
    let currentBksRoutes = null;
    let currentDepot = null;
    let routeProgress = [];
    let animationSpeed = 0.15;
    
    // Camera State per canvas
    const cameraState = {
        'cvrp-canvas': { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 },
        'bks-canvas': { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 }
    };
    
    // Base transform state
    let minX = 0, minY = 0, baseScale = 1, baseOffsetX = 0, baseOffsetY = 0;

    // Resize canvas
    function resizeCanvas() {
        if (canvas.width !== cvrpWrapper.clientWidth || canvas.height !== cvrpWrapper.clientHeight) {
            canvas.width = cvrpWrapper.clientWidth;
            canvas.height = cvrpWrapper.clientHeight;
        }
        
        if (canvasBks.width !== bksWrapper.clientWidth || canvasBks.height !== bksWrapper.clientHeight) {
            canvasBks.width = bksWrapper.clientWidth;
            canvasBks.height = bksWrapper.clientHeight;
        }
        
        if (currentRoutes) calculateBaseTransform();
    }
    
    // Use modern ResizeObserver to handle CSS transitions (0.3s width change)
    const resizeObserver = new ResizeObserver(() => {
        resizeCanvas();
    });
    resizeObserver.observe(cvrpWrapper);
    resizeObserver.observe(bksWrapper);
    resizeCanvas();
    
    // Toggle logic
    toggleBks.addEventListener('change', (e) => {
        if (e.target.checked) {
            cvrpWrapper.classList.add('split');
            bksWrapper.classList.remove('hidden');
            bksWrapper.classList.add('split');
        } else {
            cvrpWrapper.classList.remove('split');
            bksWrapper.classList.add('hidden');
            bksWrapper.classList.remove('split');
        }
        // ResizeObserver handles the canvas resolution automatically during the transition
    });
    
    // --- Camera Controls ---
    const attachCameraEvents = (element) => {
        const id = element.id;
        element.addEventListener('mousedown', (e) => {
            cameraState[id].isDragging = true;
            cameraState[id].startX = e.clientX - cameraState[id].panX;
            cameraState[id].startY = e.clientY - cameraState[id].panY;
        });
        
        element.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomSensitivity = 0.001;
            const delta = -e.deltaY * zoomSensitivity;
            
            const rect = element.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const oldZoom = cameraState[id].zoom;
            cameraState[id].zoom = Math.max(0.5, Math.min(10, cameraState[id].zoom * Math.exp(delta)));
            
            cameraState[id].panX = mouseX - (mouseX - cameraState[id].panX) * (cameraState[id].zoom / oldZoom);
            cameraState[id].panY = mouseY - (mouseY - cameraState[id].panY) * (cameraState[id].zoom / oldZoom);
        }, { passive: false });
    };

    attachCameraEvents(canvas);
    attachCameraEvents(canvasBks);
    
    window.addEventListener('mousemove', (e) => {
        ['cvrp-canvas', 'bks-canvas'].forEach(id => {
            if (cameraState[id].isDragging) {
                cameraState[id].panX = e.clientX - cameraState[id].startX;
                cameraState[id].panY = e.clientY - cameraState[id].startY;
            }
        });
    });
    
    window.addEventListener('mouseup', () => { 
        cameraState['cvrp-canvas'].isDragging = false; 
        cameraState['bks-canvas'].isDragging = false; 
    });

    // Fetch instances
    fetch('/api/instances')
        .then(res => res.json())
        .then(data => {
            select.innerHTML = '<option value="" disabled selected>Choose an instance...</option>';
            data.forEach(inst => {
                instancesMap[inst.name] = inst.path;
                const opt = document.createElement('option');
                opt.value = inst.name;
                opt.textContent = `${inst.name} (BKS: ${inst.bks || '?'})`;
                select.appendChild(opt);
            });
            btn.disabled = false;
        })
        .catch(err => {
            select.innerHTML = '<option disabled>Error loading instances</option>';
            console.error(err);
        });

    // Run Optimization
    btn.addEventListener('click', () => {
        const instanceName = select.value;
        if (!instanceName) return;

        // UI Update
        btn.disabled = true;
        select.disabled = true;
        btnText.textContent = 'Solving...';
        spinner.classList.remove('hidden');
        emptyState.classList.add('hidden');
        statStatus.textContent = 'Running HGA...';
        statStatus.style.color = '#3b82f6';
        statSimilarity.textContent = '--';
        
        // Reset state
        currentRoutes = null;
        currentDepot = null;
        cameraState['cvrp-canvas'] = { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 };
        cameraState['bks-canvas'] = { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 };
        
        if (currentAnimationId) {
            cancelAnimationFrame(currentAnimationId);
            currentAnimationId = null;
        }

        const path = instancesMap[instanceName];

        fetch(`/api/solve/${instanceName}?path=${encodeURIComponent(path)}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if(data.error) throw new Error(data.error);

                // Update Stats
                statStatus.textContent = 'Completed';
                statStatus.style.color = '#10b981';
                statCost.textContent = data.cost.toFixed(2);
                statGap.textContent = data.gap !== null ? `${data.gap.toFixed(2)}%` : 'N/A';
                statSimilarity.textContent = data.edge_similarity !== null ? `${data.edge_similarity.toFixed(1)}%` : 'N/A';
                statFes.textContent = data.fes.toLocaleString();
                statTime.textContent = `${data.execution_time_ms.toFixed(0)} ms`;
                
                // Update Instance Details
                panelDetails.style.display = 'block';
                detailCustomers.textContent = data.instance_info.customers;
                detailVehicles.textContent = data.instance_info.vehicles;
                detailCapacity.textContent = data.instance_info.capacity;

                // Render Map
                currentBksRoutes = data.bks_routes;
                if (currentBksRoutes) {
                    toggleBks.disabled = false;
                } else {
                    toggleBks.disabled = true;
                    toggleBks.checked = false;
                    toggleBks.dispatchEvent(new Event('change'));
                }
                
                initNetwork(data.routes, data.depot);
            })
            .catch(err => {
                statStatus.textContent = 'Error';
                statStatus.style.color = '#ef4444';
                console.error(err);
            })
            .finally(() => {
                btn.disabled = false;
                select.disabled = false;
                btnText.textContent = 'Run Optimization';
                spinner.classList.add('hidden');
            });
    });

    // --- Canvas Rendering Logic ---
    function calculateBaseTransform() {
        if (!currentRoutes) return;
        let maxX = currentDepot.x, maxY = currentDepot.y;
        minX = currentDepot.x; minY = currentDepot.y;
        
        currentRoutes.forEach(route => {
            route.forEach(node => {
                if (node.x < minX) minX = node.x;
                if (node.x > maxX) maxX = node.x;
                if (node.y < minY) minY = node.y;
                if (node.y > maxY) maxY = node.y;
            });
        });

        const padding = 50;
        const width = canvas.width - padding * 2;
        const height = canvas.height - padding * 2;
        
        const scaleX = width / (maxX - minX || 1);
        const scaleY = height / (maxY - minY || 1);
        baseScale = Math.min(scaleX, scaleY);

        baseOffsetX = (canvas.width - (maxX - minX) * baseScale) / 2;
        baseOffsetY = (canvas.height - (maxY - minY) * baseScale) / 2;
    }

    function transform(x, y, targetCanvas) {
        const bx = (x - minX) * baseScale + baseOffsetX;
        const by = targetCanvas.height - ((y - minY) * baseScale + baseOffsetY);
        
        const state = cameraState[targetCanvas.id];
        return {
            x: bx * state.zoom + state.panX,
            y: by * state.zoom + state.panY
        };
    }

    function initNetwork(routes, depot) {
        currentRoutes = routes;
        currentDepot = depot;
        routeProgress = routes.map(() => 0);
        calculateBaseTransform();
        
        if (!currentAnimationId) {
            renderLoop();
        }
    }
    
    const colors = [
        '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
        '#14b8a6', '#f43f5e', '#84cc16', '#6366f1', '#d946ef'
    ];

    function drawRoutes(ctxTarget, routesToDraw, isBks) {
        ctxTarget.clearRect(0, 0, ctxTarget.canvas.width, ctxTarget.canvas.height);
        const state = cameraState[ctxTarget.canvas.id];

        // 1. Draw Routes
        routesToDraw.forEach((route, i) => {
            if (!isBks) {
                if (routeProgress[i] < route.length - 1) {
                    routeProgress[i] = Math.min(routeProgress[i] + animationSpeed, route.length - 1);
                }
            }
            
            ctxTarget.strokeStyle = isBks ? '#fbbf24' : colors[i % colors.length];
            ctxTarget.lineWidth = 2 * Math.max(0.5, Math.min(state.zoom, 3));
            ctxTarget.lineCap = 'round';
            ctxTarget.lineJoin = 'round';
            
            if (isBks) {
                ctxTarget.setLineDash([10, 10]);
            } else {
                ctxTarget.setLineDash([]);
                if (state.zoom < 1.5) {
                    ctxTarget.shadowColor = ctxTarget.strokeStyle;
                    ctxTarget.shadowBlur = 5;
                }
            }

            ctxTarget.beginPath();
            const startPt = transform(route[0].x, route[0].y, ctxTarget.canvas);
            ctxTarget.moveTo(startPt.x, startPt.y);

            const currentIndex = isBks ? route.length - 1 : Math.floor(routeProgress[i]);
            
            for (let j = 1; j <= currentIndex; j++) {
                const pt = transform(route[j].x, route[j].y, ctxTarget.canvas);
                ctxTarget.lineTo(pt.x, pt.y);
            }

            if (!isBks && currentIndex < route.length - 1) {
                const pt1 = transform(route[currentIndex].x, route[currentIndex].y, ctxTarget.canvas);
                const pt2 = transform(route[currentIndex + 1].x, route[currentIndex + 1].y, ctxTarget.canvas);
                const fraction = routeProgress[i] - currentIndex;
                const curX = pt1.x + (pt2.x - pt1.x) * fraction;
                const curY = pt1.y + (pt2.y - pt1.y) * fraction;
                ctxTarget.lineTo(curX, curY);
            }

            ctxTarget.stroke();
            ctxTarget.shadowBlur = 0;
            if (isBks) ctxTarget.setLineDash([]);
        });
        
        // 2. Draw Customers
        routesToDraw.forEach((route, i) => {
            const color = isBks ? '#fbbf24' : colors[i % colors.length];
            route.forEach(node => {
                if (node.id === 0) return; // skip depot here
                const pt = transform(node.x, node.y, ctxTarget.canvas);
                
                ctxTarget.fillStyle = color;
                ctxTarget.beginPath();
                ctxTarget.arc(pt.x, pt.y, 4.5 * Math.max(0.5, Math.min(state.zoom, 2)), 0, Math.PI * 2);
                ctxTarget.fill();
                
                if (state.zoom > 1.8) {
                    ctxTarget.fillStyle = 'rgba(255, 255, 255, 0.95)';
                    ctxTarget.font = `bold ${10 * Math.max(1, Math.min(state.zoom/2, 2))}px Inter`;
                    ctxTarget.shadowColor = 'rgba(0, 0, 0, 0.9)';
                    ctxTarget.shadowBlur = 4;
                    ctxTarget.fillText(`C${node.id} (D:${node.demand})`, pt.x + 8, pt.y + 4);
                    ctxTarget.shadowBlur = 0;
                }
            });
        });

        // 3. Draw Depot
        const dPt = transform(currentDepot.x, currentDepot.y, ctxTarget.canvas);
        ctxTarget.fillStyle = '#ef4444';
        ctxTarget.shadowColor = 'rgba(239, 68, 68, 0.5)';
        ctxTarget.shadowBlur = 10;
        const depotRadius = 8 * Math.max(0.8, Math.min(state.zoom, 1.5));
        ctxTarget.beginPath();
        ctxTarget.arc(dPt.x, dPt.y, depotRadius, 0, Math.PI * 2);
        ctxTarget.fill();
        ctxTarget.shadowBlur = 0;
        
        if (state.zoom > 1.5) {
            ctxTarget.fillStyle = '#ef4444';
            ctxTarget.shadowColor = 'rgba(0, 0, 0, 0.9)';
            ctxTarget.shadowBlur = 4;
            ctxTarget.font = `bold ${12 * Math.max(1, Math.min(state.zoom/2, 2))}px Inter`;
            ctxTarget.fillText(`DEPOT`, dPt.x + depotRadius * 1.5, dPt.y + depotRadius / 2);
            ctxTarget.shadowBlur = 0;
        }
    }

    function renderLoop() {
        if (!currentRoutes) return;
        currentAnimationId = requestAnimationFrame(renderLoop);
        
        drawRoutes(ctx, currentRoutes, false);
        
        if (toggleBks.checked && currentBksRoutes) {
            drawRoutes(ctxBks, currentBksRoutes, true);
        }
    }
});

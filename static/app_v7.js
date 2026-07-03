document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('instance-select');
    const solveBtn = document.getElementById('solve-btn');
    const solveBtnText = document.getElementById('solve-btn-text');
    const spinner = document.getElementById('spinner');
    const emptyState = document.getElementById('empty-state');
    
    // Params
    const pFe = document.getElementById('param-fe');
    const pPop = document.getElementById('param-pop');
    const pMut = document.getElementById('param-mut');
    const pSeed = document.getElementById('param-seed');
    const pLs = document.getElementById('param-ls');

    // Stats
    const statStatus = document.getElementById('stat-status');
    const statCost = document.getElementById('stat-cost');
    const statGap = document.getElementById('stat-gap');
    const statFes = document.getElementById('stat-fes');
    const statTime = document.getElementById('stat-time');
    const statFeasibility = document.getElementById('stat-feasibility');

    // Panels
    const convergencePanel = document.getElementById('convergence-panel');
    const protocolPanel = document.getElementById('protocol-panel');
    const routeLegend = document.getElementById('route-legend');
    
    // Canvas & Toggles
    const cvrpWrapper = document.getElementById('cvrp-wrapper');
    const bksWrapper = document.getElementById('bks-wrapper');
    const toggleBks = document.getElementById('toggle-bks');
    
    const canvas = document.getElementById('cvrp-canvas');
    const ctx = canvas.getContext('2d');
    const canvasBks = document.getElementById('bks-canvas');
    const ctxBks = canvasBks.getContext('2d');
    
    // State
    let instancesMap = {};
    let currentAnimationId = null;
    let currentMode = 'single'; // 'single' or 'protocol'
    let convergenceChart = null;
    
    let currentRoutes = null;
    let currentBksRoutes = null;
    let currentDepot = null;
    let routeProgress = [];
    const animationSpeed = 0.2;
    let capacity = 0;
    
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f43f5e', '#84cc16', '#6366f1', '#d946ef'];
    
    // Camera
    const cameraState = {
        'cvrp-canvas': { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 },
        'bks-canvas': { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 }
    };
    let minX = 0, minY = 0, baseScale = 1, baseOffsetX = 0, baseOffsetY = 0;

    // Mobile Menu
    document.getElementById('mobile-menu-btn')?.addEventListener('click', () => document.getElementById('sidebar').classList.add('open'));
    document.getElementById('mobile-close')?.addEventListener('click', () => document.getElementById('sidebar').classList.remove('open'));

    // Resize
    const resizeObserver = new ResizeObserver(() => {
        if(canvas.width !== cvrpWrapper.clientWidth || canvas.height !== cvrpWrapper.clientHeight) {
            canvas.width = cvrpWrapper.clientWidth;
            canvas.height = cvrpWrapper.clientHeight;
        }
        if(canvasBks.width !== bksWrapper.clientWidth || canvasBks.height !== bksWrapper.clientHeight) {
            canvasBks.width = bksWrapper.clientWidth;
            canvasBks.height = bksWrapper.clientHeight;
        }
        if(currentRoutes) calculateBaseTransform();
    });
    resizeObserver.observe(cvrpWrapper);
    resizeObserver.observe(bksWrapper);

    // BKS Toggle
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
    });

    // Camera Events
    const attachCameraEvents = (element) => {
        const id = element.id;
        element.addEventListener('mousedown', (e) => {
            cameraState[id].isDragging = true;
            cameraState[id].startX = e.clientX - cameraState[id].panX;
            cameraState[id].startY = e.clientY - cameraState[id].panY;
        });
        element.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = -e.deltaY * 0.001;
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

    // Mode Toggle
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentMode = e.target.dataset.mode;
            solveBtnText.textContent = currentMode === 'single' ? 'Run Single' : 'Run Protocol';
            
            // Toggle panels immediately
            if (currentMode === 'single') {
                convergencePanel.classList.remove('hidden');
                protocolPanel.classList.add('hidden');
            } else {
                convergencePanel.classList.add('hidden');
                protocolPanel.classList.remove('hidden');
            }
        });
    });

    // Load Instances
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
            solveBtn.disabled = false;
        })
        .catch(console.error);

    // Solve
    solveBtn.addEventListener('click', () => {
        const instanceName = select.value;
        if (!instanceName) return;

        const reqBody = {
            path: instancesMap[instanceName],
            max_fe: parseInt(pFe.value) || 350000,
            pop_size: parseInt(pPop.value) || 50,
            mutation_rate: parseFloat(pMut.value) || 0.4,
            use_local_search: pLs.checked,
            seed: pSeed.value ? parseInt(pSeed.value) : null
        };

        // UI State
        solveBtn.disabled = true;
        select.disabled = true;
        solveBtnText.textContent = 'Solving...';
        spinner.classList.remove('hidden');
        emptyState.classList.add('hidden');
        statStatus.textContent = 'Running...';
        statStatus.style.color = '#3b82f6';
        
        // Reset Map
        currentRoutes = null;
        if (currentAnimationId) {
            cancelAnimationFrame(currentAnimationId);
            currentAnimationId = null;
        }
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        routeLegend.classList.add('hidden');
        routeLegend.innerHTML = '';

        if (currentMode === 'single') {
            runSingle(instanceName, reqBody);
        } else {
            runProtocol(instanceName, reqBody);
        }
    });

    function runSingle(instanceName, reqBody) {
        convergencePanel.classList.remove('hidden');
        protocolPanel.classList.add('hidden');

        fetch(`/api/solve/${instanceName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        })
        .then(res => res.json())
        .then(data => {
            if(data.error) throw new Error(data.error);
            
            capacity = data.instance_info.capacity;
            updateStats(data.cost, data.gap, data.fes, data.execution_time_ms, data.is_feasible);
            
            currentBksRoutes = data.bks_routes;
            toggleBks.disabled = !currentBksRoutes;
            if(!currentBksRoutes) {
                toggleBks.checked = false;
                toggleBks.dispatchEvent(new Event('change'));
            }
            
            initNetwork(data.routes, data.depot);
            plotConvergence(data.convergence_log);
            buildLegend(data.routes);
        })
        .catch(handleError)
        .finally(resetUI);
    }

    function runProtocol(instanceName, reqBody) {
        convergencePanel.classList.add('hidden');
        protocolPanel.classList.remove('hidden');
        
        fetch(`/api/solve-protocol/${instanceName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        })
        .then(res => res.json())
        .then(data => {
            if(data.error) throw new Error(data.error);
            
            updateStats(data.best_cost, data.gap, data.avg_fes, null, null);
            statFeasibility.textContent = 'Multi';
            statFeasibility.className = 'stat-value badge';
            statTime.textContent = '--';
            
            const tbody = document.querySelector('#protocol-table tbody');
            tbody.innerHTML = '';
            data.runs.forEach((r, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${idx + 1}</td>
                    <td>${r.seed}</td>
                    <td>${r.cost.toFixed(1)}</td>
                    <td>${r.gap ? r.gap.toFixed(2) + '%' : '-'}</td>
                    <td>${r.fes.toLocaleString()}</td>
                    <td><span class="badge ${r.is_feasible ? 'success' : 'error'}">${r.is_feasible ? 'Yes' : 'No'}</span></td>
                `;
                tbody.appendChild(tr);
            });
            
            document.getElementById('protocol-summary').innerHTML = `
                <div><strong>Best:</strong> ${data.best_cost.toFixed(1)}</div>
                <div><strong>Mean:</strong> ${data.mean_cost.toFixed(1)}</div>
                <div><strong>StdDev:</strong> ${data.std_cost.toFixed(2)}</div>
                <div><strong>Avg FE:</strong> ${Math.round(data.avg_fes).toLocaleString()}</div>
            `;
            
            capacity = data.instance_info.capacity;
            currentBksRoutes = data.bks_routes;
            toggleBks.disabled = !currentBksRoutes;
            if(!currentBksRoutes) {
                toggleBks.checked = false;
                toggleBks.dispatchEvent(new Event('change'));
            }
            
            initNetwork(data.routes, data.depot);
            buildLegend(data.routes);
        })
        .catch(handleError)
        .finally(resetUI);
    }

    function updateStats(cost, gap, fes, time, feasible) {
        statStatus.textContent = 'Completed';
        statStatus.style.color = 'var(--success)';
        statCost.textContent = cost.toFixed(2);
        statGap.textContent = gap !== null ? `${gap.toFixed(2)}%` : 'N/A';
        statFes.textContent = Math.round(fes).toLocaleString();
        
        if (time !== null) {
            statTime.textContent = `${time.toFixed(0)} ms`;
        }
        if (feasible !== null) {
            statFeasibility.textContent = feasible ? 'Feasible' : 'Violations';
            statFeasibility.className = `stat-value badge ${feasible ? 'success' : 'error'}`;
        }
    }

    function buildLegend(routes) {
        routeLegend.innerHTML = '';
        routes.forEach((route, i) => {
            const color = colors[i % colors.length];
            // Calculate demand
            const demand = route.reduce((sum, n) => sum + (n.demand || 0), 0);
            const pct = Math.round((demand / capacity) * 100);
            
            const div = document.createElement('div');
            div.className = 'legend-item';
            div.innerHTML = `
                <div class="legend-color" style="background: ${color}"></div>
                <span>R${i+1}: ${demand}/${capacity} (${pct}%)</span>
            `;
            routeLegend.appendChild(div);
        });
        routeLegend.classList.remove('hidden');
    }

    function plotConvergence(log) {
        if (!log || log.length === 0) return;
        const ctxChart = document.getElementById('convergence-chart').getContext('2d');
        
        const labels = log.map(p => p[0]);
        const data = log.map(p => p[1]);

        if (convergenceChart) convergenceChart.destroy();
        
        convergenceChart = new Chart(ctxChart, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Best Cost',
                    data: data,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    stepped: 'before'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }
                }
            }
        });
    }

    function handleError(err) {
        statStatus.textContent = 'Error';
        statStatus.style.color = 'var(--danger)';
        console.error(err);
        alert(err.message || 'An error occurred while solving.');
    }

    function resetUI() {
        solveBtn.disabled = false;
        select.disabled = false;
        solveBtnText.textContent = currentMode === 'single' ? 'Run Single' : 'Run Protocol';
        spinner.classList.add('hidden');
    }

    // Canvas Logic
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
        return { x: bx * state.zoom + state.panX, y: by * state.zoom + state.panY };
    }

    function initNetwork(routes, depot) {
        currentRoutes = routes;
        currentDepot = depot;
        routeProgress = routes.map(() => 0);
        
        // Reset Camera
        cameraState['cvrp-canvas'] = { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 };
        cameraState['bks-canvas'] = { zoom: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 };
        
        calculateBaseTransform();
        if (!currentAnimationId) renderLoop();
    }
    
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
            
            if (isBks) ctxTarget.setLineDash([8, 8]);
            else ctxTarget.setLineDash([]);

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
            if (isBks) ctxTarget.setLineDash([]);
        });
        
        // 2. Draw Customers
        routesToDraw.forEach((route, i) => {
            const color = isBks ? '#fbbf24' : colors[i % colors.length];
            route.forEach(node => {
                if (node.id === 0) return;
                const pt = transform(node.x, node.y, ctxTarget.canvas);
                ctxTarget.fillStyle = color;
                ctxTarget.beginPath();
                ctxTarget.arc(pt.x, pt.y, 4 * Math.max(0.5, Math.min(state.zoom, 2)), 0, Math.PI * 2);
                ctxTarget.fill();
                
                ctxTarget.fillStyle = '#fff';
                ctxTarget.font = `${10 * Math.max(0.8, Math.min(state.zoom/2, 2))}px Inter`;
                ctxTarget.fillText(`Customer ${node.id}, Demand ${node.demand}`, pt.x + 8, pt.y - 8);
            });
        });

        // 3. Draw Depot
        const dPt = transform(currentDepot.x, currentDepot.y, ctxTarget.canvas);
        ctxTarget.fillStyle = '#ef4444';
        const depotRadius = 7 * Math.max(0.8, Math.min(state.zoom, 1.5));
        ctxTarget.beginPath();
        ctxTarget.arc(dPt.x, dPt.y, depotRadius, 0, Math.PI * 2);
        ctxTarget.fill();

        ctxTarget.fillStyle = '#fff';
        ctxTarget.font = `bold ${12 * Math.max(0.8, Math.min(state.zoom, 1.5))}px Inter`;
        ctxTarget.fillText('Depot', dPt.x + 10, dPt.y + 4);
    }

    function renderLoop() {
        if (!currentRoutes) return;
        currentAnimationId = requestAnimationFrame(renderLoop);
        drawRoutes(ctx, currentRoutes, false);
        if (toggleBks.checked && currentBksRoutes) drawRoutes(ctxBks, currentBksRoutes, true);
    }
});

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

    // Instance details elements
    const panelDetails = document.getElementById('instance-details-panel');
    const detailCustomers = document.getElementById('detail-customers');
    const detailVehicles = document.getElementById('detail-vehicles');
    const detailCapacity = document.getElementById('detail-capacity');

    // Canvas setup
    const canvas = document.getElementById('cvrp-canvas');
    const ctx = canvas.getContext('2d');
    
    let instancesMap = {};
    let currentAnimationId = null;
    
    // Global State for rendering
    let currentRoutes = null;
    let currentDepot = null;
    let routeProgress = [];
    let animationSpeed = 0.15;
    
    // Camera State
    let cameraZoom = 1;
    let cameraPanX = 0;
    let cameraPanY = 0;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    
    // Base transform state
    let minX = 0, minY = 0, baseScale = 1, baseOffsetX = 0, baseOffsetY = 0;

    // Resize canvas
    function resizeCanvas() {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
        if (currentRoutes) calculateBaseTransform();
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
    
    // --- Camera Controls ---
    canvas.addEventListener('mousedown', (e) => {
        isDragging = true;
        dragStartX = e.clientX - cameraPanX;
        dragStartY = e.clientY - cameraPanY;
    });
    
    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        cameraPanX = e.clientX - dragStartX;
        cameraPanY = e.clientY - dragStartY;
    });
    
    window.addEventListener('mouseup', () => { isDragging = false; });
    
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomSensitivity = 0.001;
        const delta = -e.deltaY * zoomSensitivity;
        
        // Zoom around mouse pointer
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const oldZoom = cameraZoom;
        cameraZoom = Math.max(0.5, Math.min(10, cameraZoom * Math.exp(delta)));
        
        // Adjust pan to keep the point under the mouse stationary
        cameraPanX = mouseX - (mouseX - cameraPanX) * (cameraZoom / oldZoom);
        cameraPanY = mouseY - (mouseY - cameraPanY) * (cameraZoom / oldZoom);
    }, { passive: false });

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
        
        // Reset state
        currentRoutes = null;
        currentDepot = null;
        cameraZoom = 1;
        cameraPanX = 0;
        cameraPanY = 0;
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
                statFes.textContent = data.fes.toLocaleString();
                statTime.textContent = `${data.execution_time_ms.toFixed(0)} ms`;
                
                // Update Instance Details
                panelDetails.style.display = 'block';
                detailCustomers.textContent = data.instance_info.customers;
                detailVehicles.textContent = data.instance_info.vehicles;
                detailCapacity.textContent = data.instance_info.capacity;

                // Render Map
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

    function transform(x, y) {
        const bx = (x - minX) * baseScale + baseOffsetX;
        const by = canvas.height - ((y - minY) * baseScale + baseOffsetY);
        
        // Apply camera zoom and pan (mouse-anchored calculation handled in wheel event)
        return {
            x: bx * cameraZoom + cameraPanX,
            y: by * cameraZoom + cameraPanY
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

    function renderLoop() {
        if (!currentRoutes) return;
        currentAnimationId = requestAnimationFrame(renderLoop);
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 1. Draw Routes up to their progress
        currentRoutes.forEach((route, i) => {
            if (routeProgress[i] < route.length - 1) {
                routeProgress[i] = Math.min(routeProgress[i] + animationSpeed, route.length - 1);
            }
            
            const color = colors[i % colors.length];
            ctx.strokeStyle = color;
            ctx.lineWidth = 2 * Math.max(0.5, Math.min(cameraZoom, 3));
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            
            // Only add glow if fully zoomed out for performance
            if (cameraZoom < 1.5) {
                ctx.shadowColor = color;
                ctx.shadowBlur = 5;
            }

            ctx.beginPath();
            
            // Always start from depot (index 0)
            const startPt = transform(route[0].x, route[0].y);
            ctx.moveTo(startPt.x, startPt.y);

            const currentIndex = Math.floor(routeProgress[i]);
            
            // Draw all completed segments
            for (let j = 1; j <= currentIndex; j++) {
                const pt = transform(route[j].x, route[j].y);
                ctx.lineTo(pt.x, pt.y);
            }

            // Draw the fractional segment
            if (currentIndex < route.length - 1) {
                const pt1 = transform(route[currentIndex].x, route[currentIndex].y);
                const pt2 = transform(route[currentIndex + 1].x, route[currentIndex + 1].y);
                const fraction = routeProgress[i] - currentIndex;
                const curX = pt1.x + (pt2.x - pt1.x) * fraction;
                const curY = pt1.y + (pt2.y - pt1.y) * fraction;
                ctx.lineTo(curX, curY);
            }

            ctx.stroke();
            ctx.shadowBlur = 0; // reset
        });
        
        // 2. Draw Customers
        currentRoutes.forEach((route, i) => {
            const color = colors[i % colors.length];
            route.forEach(node => {
                if (node.id === 0) return; // skip depot here
                const pt = transform(node.x, node.y);
                
                // Dot
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(pt.x, pt.y, 4.5 * Math.max(0.5, Math.min(cameraZoom, 2)), 0, Math.PI * 2);
                ctx.fill();
                
                // Text Label (only if zoomed in)
                if (cameraZoom > 1.8) {
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.95)'; // Brighter white
                    ctx.font = `bold ${10 * Math.max(1, Math.min(cameraZoom/2, 2))}px Inter`;
                    ctx.shadowColor = 'rgba(0, 0, 0, 0.9)'; // Strong dark shadow for contrast
                    ctx.shadowBlur = 4;
                    ctx.fillText(`C${node.id} (D:${node.demand})`, pt.x + 8, pt.y + 4);
                    ctx.shadowBlur = 0; // reset
                }
            });
        });

        // 3. Draw Depot
        const dPt = transform(currentDepot.x, currentDepot.y);
        ctx.fillStyle = '#ef4444';
        ctx.shadowColor = 'rgba(239, 68, 68, 0.5)';
        ctx.shadowBlur = 10;
        const depotRadius = 8 * Math.max(0.8, Math.min(cameraZoom, 1.5));
        ctx.beginPath();
        ctx.arc(dPt.x, dPt.y, depotRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0; // reset
        
        if (cameraZoom > 1.5) {
            ctx.fillStyle = '#ef4444';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
            ctx.shadowBlur = 4;
            ctx.font = `bold ${12 * Math.max(1, Math.min(cameraZoom/2, 2))}px Inter`;
            ctx.fillText(`DEPOT`, dPt.x + depotRadius * 1.5, dPt.y + depotRadius / 2);
            ctx.shadowBlur = 0; // reset
        }
    }
});

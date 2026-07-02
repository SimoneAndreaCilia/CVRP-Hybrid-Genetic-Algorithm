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

    // Canvas setup
    const canvas = document.getElementById('cvrp-canvas');
    const ctx = canvas.getContext('2d');
    
    let instancesMap = {};
    let currentAnimationId = null;

    // Resize canvas
    function resizeCanvas() {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

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
        
        if (currentAnimationId) cancelAnimationFrame(currentAnimationId);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

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

                // Render Map
                renderNetwork(data.routes, data.depot);
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
    function renderNetwork(routes, depot) {
        // Find bounding box to auto-scale
        let minX = depot.x, maxX = depot.x, minY = depot.y, maxY = depot.y;
        
        routes.forEach(route => {
            route.forEach(node => {
                if (node.x < minX) minX = node.x;
                if (node.x > maxX) maxX = node.x;
                if (node.y < minY) minY = node.y;
                if (node.y > maxY) maxY = node.y;
            });
        });

        // Add padding
        const padding = 50;
        const width = canvas.width - padding * 2;
        const height = canvas.height - padding * 2;
        
        const scaleX = width / (maxX - minX || 1);
        const scaleY = height / (maxY - minY || 1);
        const scale = Math.min(scaleX, scaleY);

        const offsetX = (canvas.width - (maxX - minX) * scale) / 2;
        const offsetY = (canvas.height - (maxY - minY) * scale) / 2;

        function transform(x, y) {
            return {
                x: (x - minX) * scale + offsetX,
                y: canvas.height - ((y - minY) * scale + offsetY) // Invert Y for standard Cartesian
            };
        }

        // Draw Nodes
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw Customers
        ctx.fillStyle = '#64748b';
        routes.forEach(route => {
            route.forEach(node => {
                const pt = transform(node.x, node.y);
                ctx.beginPath();
                ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
                ctx.fill();
            });
        });

        // Draw Depot
        const dPt = transform(depot.x, depot.y);
        ctx.fillStyle = '#ef4444';
        ctx.shadowColor = 'rgba(239, 68, 68, 0.5)';
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.rect(dPt.x - 6, dPt.y - 6, 12, 12);
        ctx.fill();
        ctx.shadowBlur = 0; // reset

        // Route Colors
        const colors = [
            '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
            '#14b8a6', '#f43f5e', '#84cc16', '#6366f1', '#d946ef'
        ];

        // --- Micro-Animation of Routes ---
        let routeProgress = routes.map(() => 0); // Progress index for each route
        let animationSpeed = 0.15; // Slower, smoother speed

        function animateRoutes() {
            let stillDrawing = false;

            // Clear canvas and redraw nodes and depot every frame
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Draw Customers
            ctx.fillStyle = '#64748b';
            routes.forEach(route => {
                route.forEach(node => {
                    const pt = transform(node.x, node.y);
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
                    ctx.fill();
                });
            });

            // Draw Depot
            const dPt = transform(depot.x, depot.y);
            ctx.fillStyle = '#ef4444';
            ctx.shadowColor = 'rgba(239, 68, 68, 0.5)';
            ctx.shadowBlur = 10;
            ctx.beginPath();
            ctx.rect(dPt.x - 6, dPt.y - 6, 12, 12);
            ctx.fill();
            ctx.shadowBlur = 0; // reset

            // Draw Routes up to their progress
            routes.forEach((route, i) => {
                if (routeProgress[i] < route.length - 1) {
                    stillDrawing = true;
                    routeProgress[i] = Math.min(routeProgress[i] + animationSpeed, route.length - 1);
                }
                
                const color = colors[i % colors.length];
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                ctx.shadowColor = color;
                ctx.shadowBlur = 5;

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
            });

            ctx.shadowBlur = 0; // reset

            if (stillDrawing) {
                currentAnimationId = requestAnimationFrame(animateRoutes);
            }
        }

        // Start animation
        animateRoutes();
    }
});

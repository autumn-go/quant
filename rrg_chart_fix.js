        function drawRRGChart() {
            const canvas = document.getElementById('rrgChart');
            const ctx = canvas.getContext('2d');
            
            // 设置canvas大小
            const width = 1000;
            const height = 600;
            canvas.width = width;
            canvas.height = height;
            
            // 清除画布
            ctx.clearRect(0, 0, width, height);
            
            // 绘制设置
            const padding = 60;
            const chartWidth = width - 2 * padding;
            const chartHeight = height - 2 * padding;
            
            // 计算坐标范围
            const allTrails = Object.values(rrgData.trails);
            let minRS = 100, maxRS = 100, minMom = 100, maxMom = 100;
            allTrails.forEach(trail => {
                trail.trail.forEach(point => {
                    minRS = Math.min(minRS, point.rs_ratio);
                    maxRS = Math.max(maxRS, point.rs_ratio);
                    minMom = Math.min(minMom, point.rs_momentum);
                    maxMom = Math.max(maxMom, point.rs_momentum);
                });
            });
            
            // 添加边距，确保100在范围内
            const rsRange = maxRS - minRS;
            const momRange = maxMom - minMom;
            minRS = Math.min(minRS - rsRange * 0.1, 95);
            maxRS = Math.max(maxRS + rsRange * 0.1, 105);
            minMom = Math.min(minMom - momRange * 0.1, 95);
            maxMom = Math.max(maxMom + momRange * 0.1, 105);
            
            // 坐标转换函数
            function toX(rs) {
                return padding + (rs - minRS) / (maxRS - minRS) * chartWidth;
            }
            function toY(mom) {
                return height - padding - (mom - minMom) / (maxMom - minMom) * chartHeight;
            }
            
            // 计算数据坐标 (100, 100) 在画布上的位置
            const centerX = toX(100);
            const centerY = toY(100);
            
            // 绘制象限背景色（使用数据坐标100作为中心）
            ctx.fillStyle = 'rgba(76,175,80,0.08)';
            ctx.fillRect(centerX, padding, chartWidth - (centerX - padding), centerY - padding); // 右上 - Leading
            ctx.fillStyle = 'rgba(33,150,243,0.08)';
            ctx.fillRect(padding, padding, centerX - padding, centerY - padding); // 左上 - Improving
            ctx.fillStyle = 'rgba(244,67,54,0.08)';
            ctx.fillRect(padding, centerY, centerX - padding, chartHeight - (centerY - padding)); // 左下 - Lagging
            ctx.fillStyle = 'rgba(255,152,0,0.08)';
            ctx.fillRect(centerX, centerY, chartWidth - (centerX - padding), chartHeight - (centerY - padding)); // 右下 - Weakening
            
            // 绘制十字中心线（在数据坐标100处）
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(centerX, padding);
            ctx.lineTo(centerX, height - padding);
            ctx.moveTo(padding, centerY);
            ctx.lineTo(width - padding, centerY);
            ctx.stroke();
            ctx.setLineDash([]);
            
            // 绘制象限标签
            ctx.font = 'bold 20px Arial';
            ctx.fillStyle = 'rgba(76,175,80,0.5)';
            ctx.fillText('领涨 LEADING', width - 150, padding + 30);
            ctx.fillStyle = 'rgba(33,150,243,0.5)';
            ctx.fillText('改善 IMPROVING', padding + 10, padding + 30);
            ctx.fillStyle = 'rgba(244,67,54,0.5)';
            ctx.fillText('落后 LAGGING', padding + 10, height - padding - 10);
            ctx.fillStyle = 'rgba(255,152,0,0.5)';
            ctx.fillText('转弱 WEAKENING', width - 160, height - padding - 10);
            
            // 绘制坐标轴标签
            ctx.font = '12px Arial';
            ctx.fillStyle = '#666';
            ctx.textAlign = 'center';
            for (let i = 0; i <= 5; i++) {
                const rs = minRS + (maxRS - minRS) * i / 5;
                const x = padding + chartWidth * i / 5;
                ctx.fillText(rs.toFixed(1), x, height - padding + 20);
            }
            ctx.textAlign = 'right';
            for (let i = 0; i <= 5; i++) {
                const mom = minMom + (maxMom - minMom) * i / 5;
                const y = height - padding - chartHeight * i / 5;
                ctx.fillText(mom.toFixed(1), padding - 10, y + 4);
            }
            
            // 绘制每个行业的轨迹
            const industries = Object.values(rrgData.trails);
            industries.forEach((trailData, index) => {
                const color = industryColors[index % industryColors.length];
                const trail = trailData.trail;
                
                if (trail.length < 2) return;
                
                // 绘制轨迹线
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.beginPath();
                trail.forEach((point, i) => {
                    const x = toX(point.rs_ratio);
                    const y = toY(point.rs_momentum);
                    if (i === 0) {
                        ctx.moveTo(x, y);
                    } else {
                        ctx.lineTo(x, y);
                    }
                });
                ctx.stroke();
                
                // 绘制起点（空心圆）
                const start = trail[0];
                ctx.beginPath();
                ctx.arc(toX(start.rs_ratio), toY(start.rs_momentum), 4, 0, Math.PI * 2);
                ctx.fillStyle = 'white';
                ctx.fill();
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // 绘制终点（实心圆）
                const end = trail[trail.length - 1];
                ctx.beginPath();
                ctx.arc(toX(end.rs_ratio), toY(end.rs_momentum), 6, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();
                
                // 在终点旁标注行业名称（只显示部分，避免拥挤）
                if (index < 20) { // 只显示前20个行业的标签
                    ctx.font = '11px Arial';
                    ctx.fillStyle = color;
                    ctx.textAlign = 'left';
                    ctx.fillText(trailData.name, toX(end.rs_ratio) + 8, toY(end.rs_momentum) + 3);
                }
            });
            
            // 绘制中心点标记 (100, 100)
            ctx.beginPath();
            ctx.arc(toX(100), toY(100), 5, 0, Math.PI * 2);
            ctx.fillStyle = '#333';
            ctx.fill();
            ctx.font = 'bold 12px Arial';
            ctx.fillStyle = '#333';
            ctx.textAlign = 'center';
            ctx.fillText('基准(100,100)', toX(100), toY(100) + 20);
        }
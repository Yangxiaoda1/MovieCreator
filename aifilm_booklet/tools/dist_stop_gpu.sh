#!/bin/bash
set -u

if [[ -z "${NODE_IP_LIST:-}" ]]; then
    echo "错误: NODE_IP_LIST 未设置" >&2
    exit 1
fi

command -v pdsh >/dev/null 2>&1 || {
    echo "错误: 找不到 pdsh" >&2
    exit 1
}

export PDSH_RCMD_TYPE=ssh
node_ip=$(printf '%s' "$NODE_IP_LIST" | sed -E 's/:[0-9]+//g')
echo "节点: $node_ip"

# --orphans 会额外清理容器内已失去主进程的 multiprocessing CUDA worker。
GPU_TYPE=""
CLEAN_ORPHANS=0
for arg in "$@"; do
    case "$arg" in
        h800|h20|a100)
            if [[ -n "$GPU_TYPE" ]]; then
                echo "错误: 只能指定一个GPU型号" >&2
                exit 1
            fi
            GPU_TYPE="$arg"
            ;;
        --orphans)
            CLEAN_ORPHANS=1
            ;;
        *)
            echo "错误: 不支持的参数 '$arg'" >&2
            echo "使用方法: $0 [h800|h20|a100] [--orphans]" >&2
            exit 1
            ;;
    esac
done

if [[ -n "$GPU_TYPE" ]]; then
    gpu_types="$GPU_TYPE"
    echo "关闭占卡进程: run_gpu_half_${GPU_TYPE}.py"
else
    gpu_types="h800 h20 a100"
    echo "关闭占卡进程: run_gpu_half_*.py (所有型号)"
fi

pdsh -f 999 -w "$node_ip" \
    "collect_descendants() { \
         children=\$(pgrep -P \"\$1\" 2>/dev/null || true); \
         for child in \$children; do \
             collect_descendants \"\$child\"; \
             printf '%s ' \"\$child\"; \
         done; \
     }; \
     for gpu_type in $gpu_types; do \
         stopped=0; \
         pid_file=/tmp/run_gpu_half_\${gpu_type}_\$(id -u).pid; \
         if [ -s \"\$pid_file\" ]; then \
             pgid=\$(cat \"\$pid_file\" 2>/dev/null || true); \
             case \"\$pgid\" in \
                 ''|*[!0-9]*) echo \"无效PID文件: \$pid_file\" ;; \
                 *) \
                     if kill -0 -- \"-\$pgid\" 2>/dev/null; then \
                         echo \"停止 run_gpu_half_\${gpu_type}.py 进程组 PGID=\$pgid\"; \
                         kill -TERM -- \"-\$pgid\" 2>/dev/null || true; \
                         i=0; \
                         while [ \$i -lt 30 ] && kill -0 -- \"-\$pgid\" 2>/dev/null; do \
                             sleep 0.2; \
                             i=\$((i + 1)); \
                         done; \
                         if kill -0 -- \"-\$pgid\" 2>/dev/null; then \
                             echo \"进程组未正常退出，发送 SIGKILL: PGID=\$pgid\"; \
                             kill -KILL -- \"-\$pgid\" 2>/dev/null || true; \
                         fi; \
                         stopped=1; \
                     fi ;; \
             esac; \
             rm -f \"\$pid_file\"; \
         fi; \
         pattern=\"[r]un_gpu_half_\${gpu_type}\\.py\"; \
         roots=\$(pgrep -f \"\$pattern\" 2>/dev/null || true); \
         if [ -n \"\$roots\" ]; then \
             all_pids=\"\"; \
             for root in \$roots; do \
                 all_pids=\"\$all_pids \$(collect_descendants \"\$root\") \$root\"; \
             done; \
             echo \"清理旧方式启动的 run_gpu_half_\${gpu_type}.py: \$all_pids\"; \
             kill -TERM \$all_pids 2>/dev/null || true; \
             sleep 2; \
             kill -KILL \$all_pids 2>/dev/null || true; \
             stopped=1; \
         fi; \
         if [ \"\$stopped\" -eq 0 ]; then \
             echo \"未找到 run_gpu_half_\${gpu_type}.py 管理进程\"; \
         fi; \
     done; \
     if [ \"$CLEAN_ORPHANS\" -eq 1 ]; then \
         echo \"扫描容器内孤立的 multiprocessing CUDA worker（GPU型号不可区分）\"; \
         orphan_pids=\"\"; \
         for proc_dir in /proc/[0-9]*; do \
             pid=\${proc_dir#/proc/}; \
             [ \"\$pid\" = 1 ] && continue; \
             [ -r \"\$proc_dir/status\" ] || continue; \
             ppid=\$(awk '\$1 == \"PPid:\" {print \$2}' \"\$proc_dir/status\" 2>/dev/null || true); \
             [ \"\$ppid\" = 1 ] || continue; \
             cmdline=\$(tr '\\0' ' ' < \"\$proc_dir/cmdline\" 2>/dev/null || true); \
             case \"\$cmdline\" in \
                 *multiprocessing.spawn*|*--multiprocessing-fork*) ;; \
                 *) continue ;; \
             esac; \
             has_nvidia_fd=0; \
             for fd in \"\$proc_dir\"/fd/*; do \
                 target=\$(readlink \"\$fd\" 2>/dev/null || true); \
                 case \"\$target\" in \
                     /dev/nvidia[0-9]*|/dev/nvidiactl|/dev/nvidia-uvm|/dev/nvidia-uvm-tools) \
                         has_nvidia_fd=1; break ;; \
                 esac; \
             done; \
             if [ \"\$has_nvidia_fd\" -eq 1 ]; then \
                 orphan_pids=\"\$orphan_pids \$pid\"; \
                 echo \"发现孤立CUDA worker: PID=\$pid CMD=\$cmdline\"; \
             fi; \
         done; \
         if [ -n \"\$orphan_pids\" ]; then \
             echo \"向孤立CUDA worker发送 SIGTERM:\$orphan_pids\"; \
             kill -TERM \$orphan_pids 2>/dev/null || true; \
             sleep 2; \
             remaining=\"\"; \
             for pid in \$orphan_pids; do \
                 if kill -0 \"\$pid\" 2>/dev/null; then \
                     remaining=\"\$remaining \$pid\"; \
                 fi; \
             done; \
             if [ -n \"\$remaining\" ]; then \
                 echo \"仍未退出，发送 SIGKILL:\$remaining\"; \
                 kill -KILL \$remaining 2>/dev/null || true; \
             fi; \
         else \
             echo \"未发现符合条件的孤立CUDA worker\"; \
         fi; \
     fi"

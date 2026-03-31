import heapq

def heuristic(a, b):
    # 맨해튼 거리
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def a_star(grid, start, goal):
    rows = len(grid)
    cols = len(grid[0])

    # 이동 방향: 상, 하, 좌, 우
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (1, -1), (-1, 1), (-1, -1)]

    open_list = []
    heapq.heappush(open_list, (0, start))

    came_from = {}
    g_cost = {start: 0}
    f_cost = {start: heuristic(start, goal)}

    while open_list:
        current_f, current = heapq.heappop(open_list)

        if current == goal:
            # 경로 복원
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path

        for dx, dy in directions:
            nx = current[0] + dx
            ny = current[1] + dy
            neighbor = (nx, ny)

            # 범위 밖이면 무시
            if nx < 0 or nx >= rows or ny < 0 or ny >= cols:
                continue

            # 장애물이면 무시 (1 = 장애물)
            if grid[nx][ny] == 1:
                continue

            tentative_g = g_cost[current] + 1

            if neighbor not in g_cost or tentative_g < g_cost[neighbor]:
                came_from[neighbor] = current
                g_cost[neighbor] = tentative_g
                f_cost[neighbor] = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_list, (f_cost[neighbor], neighbor))

    return None  # 경로가 없는 경우


# 예시 맵
# 0 = 이동 가능, 1 = 장애물
grid = [
    [0, 0, 0, 0, 0],
    [1, 1, 0, 1, 0],
    [0, 0, 0, 1, 0],
    [0, 1, 1, 0, 0],
    [0, 0, 0, 0, 0]
]

start = (0, 0)
goal = (4, 4)

path = a_star(grid, start, goal)

if path:
    print("최단 경로:", path)
else:
    print("경로를 찾을 수 없습니다.")
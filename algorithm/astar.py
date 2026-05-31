import heapq


def heuristic(a, b):
    # a, b는 (x, y)
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def a_star(grid, start, goal):
    """
    grid[y][x] 기준
    start = (x, y)
    goal = (x, y)

    0 = 이동 가능
    1 = 장애물
    """

    rows = len(grid)
    cols = len(grid[0])

    def in_bounds(x, y):
        return 0 <= x < cols and 0 <= y < rows

    def is_free(x, y):
        return grid[y][x] == 0

    if not in_bounds(start[0], start[1]):
        return None

    if not in_bounds(goal[0], goal[1]):
        return None

    if not is_free(start[0], start[1]):
        return None

    if not is_free(goal[0], goal[1]):
        return None

    # x축 가로, y축 세로 기준
    # east, west, south, north
    directions = [
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1)
    ]

    open_list = []
    heapq.heappush(open_list, (0, start))

    came_from = {}
    g_cost = {start: 0}

    while open_list:
        current_f, current = heapq.heappop(open_list)

        if current == goal:
            path = [current]

            while current in came_from:
                current = came_from[current]
                path.append(current)

            path.reverse()
            return path

        current_x, current_y = current

        for dx, dy in directions:
            next_x = current_x + dx
            next_y = current_y + dy
            neighbor = (next_x, next_y)

            if not in_bounds(next_x, next_y):
                continue

            if not is_free(next_x, next_y):
                continue

            tentative_g = g_cost[current] + 1

            if neighbor not in g_cost or tentative_g < g_cost[neighbor]:
                came_from[neighbor] = current
                g_cost[neighbor] = tentative_g
                f_cost = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_list, (f_cost, neighbor))

    return None
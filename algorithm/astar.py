import heapq


def heuristic(a, b):
    # a, b는 (x, y)
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def a_star(grid, start, goal, start_direction="north", turn_penalty=0.5):
    """
    grid[y][x] 기준
    start = (x, y)
    goal = (x, y)

    0 = 이동 가능
    1 = 장애물

    start_direction:
        "east", "west", "south", "north"

    turn_penalty:
        방향이 바뀔 때 추가되는 비용
        값이 클수록 방향 전환이 적은 경로를 더 선호함
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

    # 방향 이름, dx, dy
    directions = [
        ("east", 1, 0),
        ("west", -1, 0),
        ("south", 0, 1),
        ("north", 0, -1)
    ]

    open_list = []

    # 상태: (x, y, 현재 바라보는 방향)
    start_state = (start[0], start[1], start_direction)

    heapq.heappush(open_list, (0, start_state))

    came_from = {}
    g_cost = {start_state: 0}

    best_goal_state = None

    while open_list:
        current_f, current_state = heapq.heappop(open_list)

        current_x, current_y, current_dir = current_state

        if (current_x, current_y) == goal:
            best_goal_state = current_state
            break

        for next_dir, dx, dy in directions:
            next_x = current_x + dx
            next_y = current_y + dy

            if not in_bounds(next_x, next_y):
                continue

            if not is_free(next_x, next_y):
                continue

            next_state = (next_x, next_y, next_dir)

            move_cost = 1

            if current_dir != next_dir:
                move_cost += turn_penalty

            tentative_g = g_cost[current_state] + move_cost

            if next_state not in g_cost or tentative_g < g_cost[next_state]:
                came_from[next_state] = current_state
                g_cost[next_state] = tentative_g

                f_cost = tentative_g + heuristic((next_x, next_y), goal)
                heapq.heappush(open_list, (f_cost, next_state))

    if best_goal_state is None:
        return None

    # 경로 복원
    path = []
    current = best_goal_state

    while current in came_from:
        x, y, direction = current
        path.append((x, y))
        current = came_from[current]

    path.append(start)
    path.reverse()

    return path
import movie_rating as M
rs = M.RatingSystem()
for i in range(1, 6):
    rs.add_user(f"u{i}", f"User{i}")
for c in "ABCD":
    rs.add_movie(f"m{c}", f"Movie{c}")
try: rs.rate_movie("u1","mA",6)
except ValueError: pass
try: rs.rate_movie("ux","mA",3)
except KeyError: pass
try: rs.add_user("u1","dup")
except ValueError: pass
rs.rate_movie("u1","mA",4); rs.rate_movie("u2","mA",2)
rs.rate_movie("u1","mA",2)
rs.rate_movie("u1","mB",5); rs.rate_movie("u1","mC",5)
rs.add_movie("mE","MovieE")
print("top10", rs.get_top_k_movies(10))
print("top2", rs.get_top_k_movies(2))

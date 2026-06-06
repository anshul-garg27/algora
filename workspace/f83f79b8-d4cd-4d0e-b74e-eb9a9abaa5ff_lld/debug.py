from movie_rating import *
rs = RatingSystem()
for i in range(1,6): rs.add_user(f"u{i}",f"U{i}")
for c in "ABCD": rs.add_movie(f"m{c}",f"Movie{c}")
rs.rate_movie("u1","mA",2); rs.rate_movie("u2","mA",2)
rs.rate_movie("u1","mB",5); rs.rate_movie("u1","mC",5)
print(rs.get_top_k_movies(5))

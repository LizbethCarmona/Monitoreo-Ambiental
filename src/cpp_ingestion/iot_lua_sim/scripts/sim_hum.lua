local file = io.open("humidity.txt", "w")

if file then
    while true do
        local random_hum = math.random(20, 22)
        fstr = string.format("%d\n", random_hum) 
        file:write(fstr)
    end
    file:close()
end

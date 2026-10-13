local file = io.open("temperature.txt", "w")

if file then
    while true do
        local random_temp = math.random(29, 31)
        fstr = string.format("%d\n", random_temp) 
        file:write(fstr)
    end
    file:close()
end

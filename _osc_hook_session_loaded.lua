ardour {
	["type"]    = "EditorHook",
	name        = "OSC Session loaded message",
	author      = "Boris Werner",
	description = "Send OSC Session loaded message",
}


function signals ()
	s = LuaSignal.Set()
	s:add ({[LuaSignal.SetSession] = true})
	return s
end

function factory (params)
	return function (signal, ref, ...)
		assert (signal == LuaSignal.SetSession)
		
		local uri = "osc.udp://192.168.178.31:8000"
		local tx = ARDOUR.LuaOSC.Address (uri)
		-- debug print (stdout)
		-- print (signal, ref, ...)
		tx:send ("/session/set", "i", 1)
	end
end

using System;

namespace Game.Network
{
    public static class Log
    {
        private static Action<string> _logger = (msg) => {return;};

        public static void SetLogger(Action<string> Logger) => _logger = Logger;  

        public static void WriteLog(string msg)
        {
            _logger(msg);
        }
    }
}

using System.Text;
using Game.Network;

namespace Game.Server
{
    public struct RockScissorsPaperGameContext
    {
        public string player_1;
        public string player_2;
        public GameSessionHandler session;
    };

    public class RockScissorsPaperGame
    {
        public enum Answer : int
        {
            Rock,
            Scissors,
            Paper
        }

        public RockScissorsPaperGame(RockScissorsPaperGameContext context)
        {
            _context = context;
        } 
        

        private RockScissorsPaperGameContext _context;

        public async Task<string> Play()
        {
            var queryOne = _context.session.AsyncQueryPlayer(_context.player_1, Encoding.UTF8.GetBytes("What"), 3000);
            var queryTwo = _context.session.AsyncQueryPlayer(_context.player_2, Encoding.UTF8.GetBytes("What"), 3000);

            var p1Answer = await queryOne;
            var p2Answer = await queryTwo;

            if (p1Answer.IsResponded && p2Answer.IsResponded)
            {
                Answer p1 = (Answer) BitConverter.ToInt32(p1Answer.AnswerRaw);
                Answer p2 = (Answer) BitConverter.ToInt32(p2Answer.AnswerRaw);

                switch (p1)
                {
                    case Answer.Rock:
                        if (p2 == Answer.Rock) return "Draw";
                        if (p2 == Answer.Scissors) return $"{_context.player_1} Win";
                        else return $"{_context.player_2} Win";
                    case Answer.Scissors:
                        if (p2 == Answer.Rock) return $"{_context.player_2} Win";
                        if (p2 == Answer.Scissors) return "Draw";
                        else return $"{_context.player_1} Win";
                    case Answer.Paper:
                        if (p2 == Answer.Rock) return $"{_context.player_1} Win";
                        if (p2 == Answer.Scissors) return $"{_context.player_2} Win";
                        else return "Draw";
                }
            }
            return "Error";
        }

        public async Task<bool> RunGame()
        {
            while (true)
            {                
                var result = await Play();
                Log.WriteLog($"Result : {result}");

                _context.session.BroadCastPlayer(Encoding.UTF8.GetBytes(result));
            }            
        }
    }
}
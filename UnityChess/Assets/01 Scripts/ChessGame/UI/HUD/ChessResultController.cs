using UnityEngine;
using TMPro;
using events.ui;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
using Core.StateManagement;

namespace UI.HUD
{
    public class ChessResultController : MonoBehaviour
    {
        [SerializeField] private ChessUIEventBus eventBus;

        [SerializeField] private TMP_Text resultText;
        [SerializeField] private TMP_Text winnerText;

        [SerializeField] private TMP_Text player1Text;
        [SerializeField] private TMP_Text player2Text;

        [SerializeField] private TMP_Text player1DeckText;
        [SerializeField] private TMP_Text player2DeckText;

        [SerializeField] private Button goToLobbyButton;
        [SerializeField] private string LobbySceneName;

        private void GoToLobby()
        {            
            NetworkManagerUnity.Instance.Session.Disconnect();
            //SceneManager.LoadScene(LobbySceneName);
        }

        public void ShowResult(GameStateStore state, string winner, string[] playerNames)
        {
            resultText.text = winner == state.LocalPlayerId ? "승리!" : "패배";

            player1Text.text = $"{playerNames[0]}";
            player2Text.text = $"{playerNames[1]}";

            //layer1DeckText.text = $"{player1Deck}";
            //player2DeckText.text = $"{player2Deck}";

            goToLobbyButton.onClick.AddListener(GoToLobby);
        }
    }
}

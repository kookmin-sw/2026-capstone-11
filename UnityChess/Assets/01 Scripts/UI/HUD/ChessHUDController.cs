using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Core;
using System.Linq;
using Core.StateManagement;

namespace UI.HUD
{
    public class ChessHUDController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private ChessGameManager gameManager;
        [SerializeField] private ChessUIController uiController;

        [Header("HUD")]
        [SerializeField] private TMP_Text turnText;
        [SerializeField] private Transform[] turnIndicators;
        [SerializeField] private Button turnEndButton;
        [SerializeField] private TMP_Text[] playerText;

        [Header("Local Player")]
        [SerializeField] private string localPlayerId = "Player1";

        private int localTurnCount = 1;
        private string lastActivePlayerId = string.Empty;
        private string firstPlayerId = string.Empty;
        private bool isInitialized = false;

        private void Start()
        {
            Init();
        }

        private void OnDestroy()
        {
            if (turnEndButton != null && uiController != null)
            {
                turnEndButton.onClick.RemoveListener(uiController.OnClickTurnEnd);
            }
        }

        private void Init()
        {
            if (turnEndButton != null && uiController != null)
            {
                turnEndButton.onClick.AddListener(uiController.OnClickTurnEnd);
            }
        }

        /// <summary>
        /// 스냅샷 적용 이후 호출해서 HUD를 갱신
        /// </summary>
        public void RefreshHUD(string localPlayerId, string[] playerNames, bool isLocalPlayerP1)
        {
            if (gameManager == null || gameManager.State == null)
            {
                Debug.LogWarning("[ChessHUDController] gameManager or State is null.");
                return;
            }

            string currentActivePlayerId = gameManager.State.ActivePlayerId;

            if (string.IsNullOrWhiteSpace(currentActivePlayerId))
            {
                Debug.LogWarning("[ChessHUDController] ActivePlayerId is empty.");
                return;
            }

            if (!isInitialized)
            {
                isInitialized = true;
                localTurnCount = 1;
                firstPlayerId = currentActivePlayerId;
                lastActivePlayerId = currentActivePlayerId;
            }
            else
            {
                bool myTurnStartedNow =
                    lastActivePlayerId != firstPlayerId &&
                    currentActivePlayerId == firstPlayerId;

                if (myTurnStartedNow)
                {
                    localTurnCount++;
                }

                lastActivePlayerId = currentActivePlayerId;
            }

            bool isMyTurn = currentActivePlayerId == localPlayerId;

            UpdateTurnText();
            UpdateTurnIndicators(isMyTurn);
            UpdatePlayerTexts(playerNames);
            UpdateTurnEndButton(isMyTurn);
            UpdateInputLock(isMyTurn);
        }

        private void UpdateTurnText()
        {
            if (turnText == null)
                return;

            turnText.text = $"{localTurnCount}";
        }

        private void UpdateTurnIndicators(bool isMyTurn)
        {
            if (isMyTurn)
            {
                turnIndicators[0].gameObject.SetActive(true);
                turnIndicators[1].gameObject.SetActive(false);
            }
            else
            {
                turnIndicators[0].gameObject.SetActive(false);
                turnIndicators[1].gameObject.SetActive(true);
            }
        }

        private void UpdatePlayerTexts(string[] playerNames)
        {
            playerText[0].text = playerNames[0];
            playerText[1].text = playerNames[1];
        }

        private void UpdateTurnEndButton(bool isMyTurn)
        {
            if (turnEndButton == null)
                return;

            turnEndButton.gameObject.SetActive(isMyTurn);
            turnEndButton.interactable = isMyTurn;
        }

        private void UpdateInputLock(bool isMyTurn)
        {
            if (uiController == null)
                return;

            uiController.SetInputLocked(!isMyTurn);
        }
    }
}
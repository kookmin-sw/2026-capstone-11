using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Core;
using System.Linq;
using Core.StateManagement;
using NUnit.Framework;

namespace UI.HUD
{
    public class ChessHUDController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private ChessGameManager gameManager;
        [SerializeField] private ChessUIController uiController;

        [Header("HUD")]
        [SerializeField] private TMP_Text oppoCardCount;
        [SerializeField] private TMP_Text turnText;
        [SerializeField] private Transform[] turnIndicators;
        [SerializeField] private Button turnEndButton;
        [SerializeField] private TMP_Text[] playerText;

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
        public void RefreshHUD(GameStateStore state, string[] playerNames, bool isLocalPlayerP1)
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

            bool isMyTurn = currentActivePlayerId == state.LocalPlayerId;

            Debug.Log($"is my turn? {isMyTurn} (ActivePlayerId: {currentActivePlayerId}, LocalPlayerId: {state.LocalPlayerId})");

            UpdateTurnText(state.TurnCnt);
            UpdateTurnIndicators(isMyTurn);
            UpdatePlayerTexts(playerNames, isLocalPlayerP1);
            UpdateOppoCardCountText(state.GetHand(isLocalPlayerP1 ? playerNames[1] : playerNames[0]).Count);
            UpdateTurnEndButton(isMyTurn);
            UpdateInputLock(isMyTurn);
        }

        private void UpdateTurnText(int turnNum)
        {
            if (turnText == null)
                return;

            turnText.text = $"{turnNum}";
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

        private void UpdatePlayerTexts(string[] playerNames, bool isP1)
        {
            if (isP1)
            {
                playerText[0].text = playerNames[0];
                playerText[1].text = playerNames[1];
            }
            else
            {
                playerText[0].text = playerNames[1];
                playerText[1].text = playerNames[0];
            }
        }

        private void UpdateOppoCardCountText(int conut)
        {
            oppoCardCount.text = conut.ToString();
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
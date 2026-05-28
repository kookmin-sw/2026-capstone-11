using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using DG.Tweening;
using Game.Network;
using TMPro;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;

namespace Title.UI
{
    [Serializable]
    public enum TitleState
    {
        WaitingForInput,
        LoginPanelOpened,
        RegisterPanelOpened,
        Transitioning,
    }

    public class TitleInputController : MonoBehaviour
    {
        [SerializeField] private TMP_Text pressAnyKeyView;

        [SerializeField] private TMP_Text infoText;
        [SerializeField] private TMP_Text nameText;

        [SerializeField] private GameObject loginPanel;
        [SerializeField] private string LobbyScene;

        [SerializeField] private Button loginButton;
        [SerializeField] private Button logoutButton;
        [SerializeField] private Button registerButton;

        private Tween infoTween;

        private TitleState inputState = TitleState.WaitingForInput;

        private void Start()
        {
            PlayFabAccountManager.Instance.AutoLogin(
                onSuccess: ShowAutoLoginResult,
                onFail: _ => ShowAutoLoginResult()
            );

            var viewTween = pressAnyKeyView
                .DOColor(Color.clear, 3f)
                .SetLoops(-1, LoopType.Yoyo);
        }

        private void Update()
        {
            if (inputState != TitleState.WaitingForInput)
                return;

            bool keyboardPressed = Keyboard.current.anyKey.wasPressedThisFrame;

            bool mousePressed = Mouse.current.leftButton.wasPressedThisFrame;

            // UI 클릭이면 무시
            if (mousePressed && EventSystem.current.IsPointerOverGameObject())
                return;

            bool pressed = keyboardPressed || mousePressed;

            if (!pressed)
                return;

            if (PlayFabAccountManager.Instance.IsLoggedIn)
                EnterLobby();
            else
                OpenLoginPanel();
        }

        private void OpenLoginPanel()
        {
            loginPanel.SetActive(true);    
        }

        private void EnterLobby()
        {
            inputState = TitleState.Transitioning;
            SceneManager.LoadScene(LobbyScene);
        }

        private void ShowAutoLoginResult()
        {
            infoTween?.Kill();

            bool isLoggedIn = PlayFabAccountManager.Instance.IsLoggedIn;

            infoText.text = isLoggedIn ? "로그인 성공!" : "로그인 실패!";

            if (isLoggedIn) 
                nameText.text = "환영합니다, " + PlayFabAccountManager.Instance.InGameDisplayName + "님";
            
            loginButton.gameObject.SetActive(!isLoggedIn);
            logoutButton.gameObject.SetActive(isLoggedIn);
            registerButton.gameObject.SetActive(!isLoggedIn);
        
            infoTween = infoText.DOColor(Color.clear, 5f);
        }

        public void SetState(TitleState state)
        {
            inputState = state;
        }

        public void OkToInput()
        {
            inputState = TitleState.WaitingForInput;
        }
    }
}
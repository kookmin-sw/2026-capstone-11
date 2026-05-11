using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using DG.Tweening;
using Game.Network;
using TMPro;
using UnityEngine.UI;

namespace Title.UI
{
    public class TitleInputController : MonoBehaviour
    {
        [SerializeField] private TMP_Text pressAnyKeyView;
        [SerializeField] private TMP_Text infoText;

        [SerializeField] private GameObject loginPanel;
        [SerializeField] private string LobbyScene;

        [SerializeField] private Button loginButton;
        [SerializeField] private Button logoutButton;

        private Tween viewTween;
        private Tween infoTween;

        private bool started = false;

        private void Start()
        {
            PlayFabAccountManager.Instance.AutoLogin(
                onSuccess: ShowAutoLoginResult,
                onFail: _ => ShowAutoLoginResult()
            );

            bool isLoggedIn = PlayFabAccountManager.Instance.IsLoggedIn;

            loginButton.gameObject.SetActive(!isLoggedIn);
            logoutButton.gameObject.SetActive(isLoggedIn);

            viewTween = pressAnyKeyView
                .DOColor(Color.clear, 2f)
                .SetLoops(-1, LoopType.Yoyo);
        }

        private void Update()
        {
            if (started)
                return;
            
            bool pressed =
                Keyboard.current.anyKey.wasPressedThisFrame ||
                Mouse.current.leftButton.wasPressedThisFrame;
            
            if (!pressed)
                return;
            
            started = true;

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
            SceneManager.LoadScene(LobbyScene);
        }

        private void ShowAutoLoginResult()
        {
            infoTween?.Kill();

            infoText.text = PlayFabAccountManager.Instance.IsLoggedIn ?
                "로그인 성공!" : "로그인 실패!";
        
            infoTween = infoText.DOColor(Color.clear, 5f);
        }
    }
}
// Esconde os campos de senha quando a escolha é enviar o link. Sem
// JavaScript o formulário continua funcionando: os campos só ficam
// visíveis, e o servidor ignora o que vier neles no modo de link.
(function () {
  var campos = document.querySelectorAll('[data-senha-manual]');
  var opcoes = document.querySelectorAll('input[name="usable_password"]');

  function atualizar() {
    var marcada = document.querySelector('input[name="usable_password"]:checked');
    var manual = marcada && marcada.value === 'true';
    campos.forEach(function (campo) { campo.hidden = !manual; });
  }

  opcoes.forEach(function (opcao) { opcao.addEventListener('change', atualizar); });
  atualizar();
})();
